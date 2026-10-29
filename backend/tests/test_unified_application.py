"""Unified role and shared telemetry checks."""
import asyncio
import secrets
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect
import app.auth as auth_module
import app.telemetry as telemetry_module
import app.api.auth_routes as auth_routes
import app.api.security_routes as security_routes
import app.api.simulator_routes as simulator_routes
import app.api.telemetry_routes as telemetry_routes
import app.api.report_routes as report_routes
import app.api.sentinel_routes as sentinel_routes
from app.auth import SecurityService, require_monitor
from app.models import Base
from app.simulator import VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore

ORIGIN = 'http://localhost:5173'
class Clock:
    value = 100.0
    def __call__(self): return self.value

class UnifiedApplicationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.security = SecurityService(self.engine)
        self.passwords = {name: secrets.token_urlsafe(18) for name in ('admin', 'virtual')}
        for name, role in (('admin', 'ADMIN'), ('virtual', 'VIRTUAL')):
            self.security.create_if_missing(name, self.passwords[name], role)
        self.clock = Clock()
        self.telemetry = TelemetryCoordinator(VirtualSpacecraftSimulator(clock=self.clock), TelemetryStore(self.engine, b'unified-test-key-32-bytes-long!!!!'))
        app = FastAPI()
        app.include_router(auth_routes.router)
        app.include_router(simulator_routes.router)
        app.include_router(telemetry_routes.router)
        for router in (security_routes.router, report_routes.router, sentinel_routes.router):
            app.include_router(router, dependencies=[Depends(require_monitor)])
        self.patches = ExitStack()
        for module in (auth_module, auth_routes, security_routes, report_routes, simulator_routes):
            self.patches.enter_context(patch.object(module, 'security', self.security))
        for module in (simulator_routes, telemetry_routes, sentinel_routes):
            self.patches.enter_context(patch.object(module, 'telemetry', self.telemetry))
        self.patches.enter_context(patch.object(telemetry_module, 'telemetry', self.telemetry))
        self.app = app
        self.clients = []
    def tearDown(self):
        for client in self.clients: client.close()
        self.patches.close()
        self.engine.dispose()
    def login(self, name):
        client = TestClient(self.app)
        self.clients.append(client)
        response = client.post('/api/v1/auth/login', json={'username': name, 'password': self.passwords[name]}, headers={'Origin': ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        return client, {'Origin': ORIGIN, 'X-CSRF-Token': response.json()['csrf_token']}
    def test_shared_temperature_roles_and_logout(self):
        virtual, vh = self.login('virtual')
        admin, ah = self.login('admin')
        for url in ('/api/v1/telemetry/state', '/api/v1/security/overview', '/api/v1/reports/runs', '/api/v1/sentinel/overview'):
            self.assertEqual(virtual.get(url).status_code, 403, url)
        self.assertEqual(admin.get('/api/v1/virtual-device').status_code, 403)
        self.assertEqual(admin.post('/api/v1/virtual-device/start', headers=ah).status_code, 403)
        with self.assertRaises(WebSocketDisconnect):
            with virtual.websocket_connect('/api/v1/telemetry/ws', headers={'Origin': ORIGIN}): pass
        with self.assertRaises(WebSocketDisconnect):
            with admin.websocket_connect('/api/v1/virtual-device/ws', headers={'Origin': ORIGIN}): pass
        response = virtual.post('/api/v1/virtual-device/start', json={'scenario': 'NORMAL_MISSION'}, headers=vh)
        self.assertEqual(response.status_code, 200, response.text)
        self.clock.value += 2
        asyncio.run(self.telemetry.tick())
        device = virtual.get('/api/v1/virtual-device/state').json()['device']
        monitor = admin.get('/api/v1/telemetry/state').json()
        self.assertEqual(device['sensors']['temperature_1_c'], monitor['latest_sample']['sensors']['temperature_1_c'])
        with admin.websocket_connect('/api/v1/telemetry/ws', headers={'Origin': ORIGIN}) as ws:
            self.assertEqual(ws.receive_json()['latest_sample']['sensors']['temperature_1_c'], device['sensors']['temperature_1_c'])
        self.assertEqual(virtual.post('/api/v1/virtual-device/pause', headers=vh).status_code, 200)
        self.assertEqual(admin.get('/api/v1/telemetry/state').json()['device']['status'], 'PAUSED')
        self.assertEqual(virtual.post('/api/v1/virtual-device/resume', headers=vh).status_code, 200)
        self.assertEqual(virtual.post('/api/v1/virtual-device/reset', headers=vh).status_code, 200)
        self.assertEqual(virtual.post('/api/v1/auth/logout', headers=vh).status_code, 204)
        self.assertEqual(virtual.get('/api/v1/virtual-device/state').status_code, 401)
        with self.assertRaises(WebSocketDisconnect):
            with virtual.websocket_connect('/api/v1/virtual-device/ws', headers={'Origin': ORIGIN}): pass
    def test_anomaly_rejection_and_isolated_reports(self):
        virtual, vh = self.login('virtual')
        admin, _ = self.login('admin')
        started = virtual.post('/api/v1/virtual-device/start', json={'scenario': 'TEMPERATURE_ANOMALY'}, headers=vh)
        self.assertEqual(started.status_code, 200, started.text)
        hot_run = started.json()['run_id']
        self.clock.value += 35
        asyncio.run(self.telemetry.tick())
        hot = admin.get('/api/v1/telemetry/state').json()
        self.assertEqual(hot['run']['run_id'], hot_run)
        self.assertTrue(hot['rule_alerts'])
        self.assertEqual(virtual.post('/api/v1/virtual-device/end', headers=vh).status_code, 200)
        started = virtual.post('/api/v1/virtual-device/start', json={'scenario': 'INVALID_SIGNATURE'}, headers=vh)
        self.assertEqual(started.status_code, 200, started.text)
        rejected_run = started.json()['run_id']
        self.clock.value += 12
        asyncio.run(self.telemetry.tick())
        state = admin.get('/api/v1/telemetry/state').json()
        self.assertEqual(state['run']['run_id'], rejected_run)
        self.assertIn('INTEGRITY_REJECTED', [row['reason_code'] for row in state['rejections']])
        history = admin.get(f'/api/v1/telemetry/runs/{rejected_run}/samples').json()['samples']
        self.assertNotIn(10, [row['sequence_number'] for row in history])
        incidents = admin.get('/api/v1/security/overview').json()['incidents']
        self.assertIn('INTEGRITY_REJECTED', [row['reason_code'] for row in incidents])
        attempts = virtual.get('/api/v1/virtual-device/state').json()['deliveries']
        self.assertIn('INTEGRITY_REJECTED', [row['reason_code'] for row in attempts])
        runs = admin.get('/api/v1/reports/runs').json()
        self.assertIn(hot_run, [row['run_id'] for row in runs])
        self.assertIn(rejected_run, [row['run_id'] for row in runs])
        self.assertEqual(virtual.get(f'/api/v1/reports/runs/{hot_run}').status_code, 403)

    def test_switching_accounts_revokes_prior_session(self):
        browser, _ = self.login('admin')
        previous = browser.cookies.get('orbitra_session')
        response = browser.post('/api/v1/auth/login', json={'username': 'virtual',
            'password': self.passwords['virtual']}, headers={'Origin': ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['role'], 'VIRTUAL')
        self.assertIsNone(self.security.authenticate(previous))
        self.assertEqual(browser.get('/api/v1/telemetry/state').status_code, 403)
        self.assertEqual(browser.get('/api/v1/virtual-device/state').status_code, 200)
    def test_open_websockets_close_after_logout(self):
        admin, ah = self.login('admin')
        with admin.websocket_connect('/api/v1/telemetry/ws', headers={'Origin': ORIGIN}) as ws:
            self.assertEqual(ws.receive_json()['type'], 'simulation_status')
            self.assertEqual(admin.post('/api/v1/auth/logout', headers=ah).status_code, 204)
            with self.assertRaises(WebSocketDisconnect): ws.receive_json()
        virtual, vh = self.login('virtual')
        with virtual.websocket_connect('/api/v1/virtual-device/ws', headers={'Origin': ORIGIN}) as ws:
            self.assertEqual(ws.receive_json()['type'], 'device_state')
            self.assertEqual(virtual.post('/api/v1/auth/logout', headers=vh).status_code, 204)
            with self.assertRaises(WebSocketDisconnect): ws.receive_json()
    def test_three_cyber_simulations_are_observed_and_reported(self):
        virtual, vh = self.login('virtual')
        admin, ah = self.login('admin')
        cases = (
            ('REPLAYED_TELEMETRY', 'REPLAY_REJECTED', 'REPLAY', 'communications'),
            ('SPOOFED_TELEMETRY', 'SOURCE_REJECTED', 'SPOOFING', 'communications'),
            ('INVALID_SIGNATURE', 'INTEGRITY_REJECTED', 'INTEGRITY', 'thermal'),
        )
        for scenario, reason_code, test_kind, block in cases:
            started = virtual.post('/api/v1/virtual-device/start', json={'scenario': scenario}, headers=vh)
            self.assertEqual(started.status_code, 200, started.text)
            run_id = started.json()['run_id']
            self.clock.value += 12
            asyncio.run(self.telemetry.tick())
            state = admin.get('/api/v1/telemetry/state').json()
            self.assertEqual(state['run']['run_id'], run_id)
            self.assertIn(reason_code, [row['reason_code'] for row in state['rejections']])
            self.assertIn(block, state['trust']['untrusted_blocks'])
            samples = admin.get(f'/api/v1/telemetry/runs/{run_id}/samples').json()['samples']
            self.assertNotIn(10, [row['sequence_number'] for row in samples])
            self.assertGreater(len(samples), 9)
            detail = [item for item in admin.get('/api/v1/security/overview').json()['incidents']
                      if item['run_id'] == run_id and item['reason_code'] == reason_code][0]['detail']
            self.assertEqual(detail['test_kind'], test_kind)
            self.assertEqual(detail['observed_reason_code'], reason_code)
            self.assertEqual(detail['outcome'], 'REJECTED')
            self.assertEqual(detail['affected_block'], block)
            if test_kind == 'SPOOFING':
                self.assertEqual(detail['mitre']['code'], 'T1692.002')
                self.assertFalse(detail['checks']['source_valid'])
            else:
                self.assertIsNone(detail['mitre'])
            if test_kind == 'INTEGRITY':
                self.assertFalse(detail['checks']['signature_valid'])
            if test_kind == 'REPLAY':
                self.assertTrue(detail['checks']['replay_detected'])
            report = admin.get(f'/api/v1/reports/runs/{run_id}').json()['cyber_security']
            self.assertEqual((report['total'], report['detected'], report['rejected'], report['accepted']), (1, 1, 1, 0))
            self.assertEqual(report['detection_rate_percent'], 100.0)
            self.assertEqual(report['rejection_reasons'], {reason_code: 1})
            self.assertEqual(virtual.get(f'/api/v1/reports/runs/{run_id}').status_code, 403)
            self.assertEqual(admin.post('/api/v1/virtual-device/reset', headers=ah).status_code, 403)
            self.assertEqual(virtual.post('/api/v1/virtual-device/end', headers=vh).status_code, 200)

    def test_cyber_rate_uses_observed_outcomes(self):
        from app.cyber_demo import summarize_tests
        rows = [
            {'packet_id': 'one', 'sequence_number': 1, 'received_at': '2026-01-01T00:00:00+00:00',
             'accepted': False, 'explanation': 'Rejected',
             'evidence': {'test_kind': 'REPLAY', 'rejection_code': 'REPLAY_REJECTED'}},
            {'packet_id': 'two', 'sequence_number': 2, 'received_at': '2026-01-01T00:00:01+00:00',
             'accepted': True, 'explanation': 'Accepted', 'evidence': {'test_kind': 'SPOOFING'}},
        ]
        result = summarize_tests(rows)
        self.assertEqual((result['total'], result['detected'], result['rejected'], result['accepted']), (2, 1, 1, 1))
        self.assertEqual(result['detection_rate_percent'], 50.0)
        self.assertIsNone(summarize_tests([])['detection_rate_percent'])
