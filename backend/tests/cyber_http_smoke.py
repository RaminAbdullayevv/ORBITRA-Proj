"""Real local HTTP/WebSocket demo against a disposable SQLite backup.

Set ORBITRA_TEST_ADMIN_PASSWORD and ORBITRA_TEST_VIRTUAL_PASSWORD in the shell.
The script never sends a request beyond 127.0.0.1 and never edits orbitra.db.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect

root = Path(__file__).resolve().parents[1]
source = sqlite3.connect(root / 'orbitra.db')
test_db = root / 'orbitra-cyber-smoke.db'
copy = sqlite3.connect(test_db)
try:
    source.backup(copy)
finally:
    source.close()
    copy.close()

origin = 'http://127.0.0.1:8013'
env = os.environ.copy()
env.update(DATABASE_URL='sqlite:///./orbitra-cyber-smoke.db', FRONTEND_ORIGIN=origin)
server = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8013'],
    cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
)
try:
    with httpx.Client(base_url=origin, timeout=10, trust_env=False) as virtual, \
         httpx.Client(base_url=origin, timeout=10, trust_env=False) as admin:
        for _ in range(80):
            if server.poll() is not None:
                raise RuntimeError('Local backend exited')
            try:
                if admin.get('/api/v1/health').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Local backend did not start')
        assert admin.get('/login').status_code == 200
        vr = virtual.post('/api/v1/auth/login', json={
            'username': 'virtual', 'password': os.environ['ORBITRA_TEST_VIRTUAL_PASSWORD']},
            headers={'Origin': origin})
        ar = admin.post('/api/v1/auth/login', json={
            'username': 'admin', 'password': os.environ['ORBITRA_TEST_ADMIN_PASSWORD']},
            headers={'Origin': origin})
        assert vr.status_code == ar.status_code == 200, (vr.text, ar.text)
        vh = {'Origin': origin, 'X-CSRF-Token': vr.json()['csrf_token']}
        ah = {'Origin': origin, 'X-CSRF-Token': ar.json()['csrf_token']}
        assert virtual.get('/api/v1/security/overview').status_code == 403
        assert admin.post('/api/v1/virtual-device/start', headers=ah).status_code == 403
        cases = (
            ('REPLAYED_TELEMETRY', 'REPLAY_REJECTED', 'communications'),
            ('SPOOFED_TELEMETRY', 'SOURCE_REJECTED', 'communications'),
            ('INVALID_SIGNATURE', 'INTEGRITY_REJECTED', 'thermal'),
        )
        cookie = 'orbitra_session=' + admin.cookies.get('orbitra_session')
        for scenario, expected, block in cases:
            with connect('ws://127.0.0.1:8013/api/v1/telemetry/ws', origin=origin,
                         additional_headers={'Cookie': cookie}, open_timeout=5, close_timeout=2) as ws:
                start = virtual.post('/api/v1/virtual-device/start', json={'scenario': scenario}, headers=vh)
                assert start.status_code == 200, start.text
                run_id = start.json()['run_id']
                deadline = time.monotonic() + 18
                while time.monotonic() < deadline:
                    event = json.loads(ws.recv(timeout=max(.2, deadline - time.monotonic())))
                    if event.get('type') == 'telemetry_rejected' and event.get('run_id') == run_id:
                        assert event['reason_code'] == expected, event
                        break
                else:
                    raise AssertionError(f'{scenario}: no live rejection over WebSocket')
            state = admin.get('/api/v1/telemetry/state').json()
            assert block in state['trust']['untrusted_blocks'], (scenario, state['trust'])
            history = admin.get(f'/api/v1/telemetry/runs/{run_id}/samples').json()['samples']
            assert 10 not in [row['sequence_number'] for row in history], scenario
            incidents = admin.get('/api/v1/security/overview').json()['incidents']
            detail = next(item['detail'] for item in incidents if item['run_id'] == run_id and item['reason_code'] == expected)
            assert detail['outcome'] == 'REJECTED' and detail['affected_block'] == block
            report = admin.get(f'/api/v1/reports/runs/{run_id}').json()['cyber_security']
            assert (report['total'], report['detected'], report['rejected'], report['accepted']) == (1, 1, 1, 0), report
            assert report['detection_rate_percent'] == 100.0, report
            assert virtual.post('/api/v1/virtual-device/end', headers=vh).status_code == 200
            print(f'{scenario}: {expected}, WS+DB+Security+Report OK')
        assert virtual.post('/api/v1/auth/logout', headers=vh).status_code == 204
        assert virtual.get('/api/v1/virtual-device/state').status_code == 401
        print('CYBER_HTTP_WS_THREE_TESTS_AND_ROLES_OK')
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)
    for _ in range(20):
        try:
            test_db.unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(.25)
