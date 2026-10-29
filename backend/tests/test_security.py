import asyncio
import secrets
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

import app.auth as auth_module
import app.api.auth_routes as auth_routes
import app.api.security_routes as security_routes
import app.api.simulator_routes as simulator_routes
import app.api.telemetry_routes as telemetry_routes
import app.api.report_routes as report_routes
from app.auth import SecurityService, require_monitor
from app.integrity import SignedTelemetryPacket
from app.models import AuditEvent, Base, OperatorEvent, RejectedTelemetry, SecurityIncident, TelemetrySample, User
from app.simulator import VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore


ORIGIN = "http://localhost:5173"
KEY = b"stage-seven-test-key-only-for-unit-tests"


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds: int):
        self.value += seconds


class SecurityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.security = SecurityService(self.engine)
        self.clock = Clock()
        self.device = VirtualSpacecraftSimulator(clock=self.clock)
        self.telemetry = TelemetryCoordinator(self.device, TelemetryStore(self.engine, KEY))
        self.passwords = {name: secrets.token_urlsafe(18) for name in ("operator", "analyst", "observer")}
        for name, role in (("operator", "VIRTUAL"), ("analyst", "SECURITY_ANALYST"), ("observer", "OBSERVER")):
            self.security.upsert_demo_user(name, self.passwords[name], role)
        app = FastAPI()
        app.include_router(auth_routes.router)
        app.include_router(simulator_routes.router)
        app.include_router(telemetry_routes.router)
        for router in (security_routes.router, report_routes.router):
            app.include_router(router, dependencies=[Depends(require_monitor)])
        self.patches = ExitStack()
        self.patches.enter_context(patch.object(auth_module, "security", self.security))
        self.patches.enter_context(patch.object(auth_routes, "security", self.security))
        self.patches.enter_context(patch.object(security_routes, "security", self.security))
        self.patches.enter_context(patch.object(report_routes, "security", self.security))
        self.patches.enter_context(patch.object(simulator_routes, "telemetry", self.telemetry))
        self.patches.enter_context(patch.object(telemetry_routes, "telemetry", self.telemetry))
        self.app = app
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.patches.close()
        self.engine.dispose()

    def client_for(self, name: str) -> tuple[TestClient, str]:
        client = TestClient(self.app)
        self.clients.append(client)
        response = client.post("/api/v1/auth/login", json={"username": name, "password": self.passwords[name]},
                               headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["role"], {"operator": "VIRTUAL", "analyst": "SECURITY_ANALYST", "observer": "OBSERVER"}[name])
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        return client, response.json()["csrf_token"]

    @staticmethod
    def headers(csrf: str) -> dict[str, str]:
        return {"Origin": ORIGIN, "X-CSRF-Token": csrf}

    def test_auth_roles_csrf_logout_and_websocket(self):
        anonymous = TestClient(self.app)
        self.clients.append(anonymous)
        self.assertEqual(anonymous.get("/api/v1/telemetry/state").status_code, 401)
        self.assertEqual(anonymous.get("/api/v1/security/overview").status_code, 401)
        with self.assertRaises(WebSocketDisconnect):
            with anonymous.websocket_connect("/api/v1/telemetry/ws", headers={"Origin": ORIGIN}):
                pass

        operator, op_csrf = self.client_for("operator")
        self.assertEqual(operator.post("/api/v1/virtual-device/start", headers={"Origin": ORIGIN}).status_code, 403)
        started = operator.post("/api/v1/virtual-device/start", headers=self.headers(op_csrf),
                                json={"scenario": "NORMAL_MISSION"})
        self.assertEqual(started.status_code, 200, started.text)
        run_id = started.json()["run_id"]
        with Session(self.engine) as db:
            operator_id = db.scalar(select(User.id).where(User.username == "operator"))
            self.assertEqual(db.scalar(select(OperatorEvent.user_id).where(OperatorEvent.run_id == run_id,
                                                                           OperatorEvent.action == "start")), operator_id)

        observer, obs_csrf = self.client_for("observer")
        self.assertEqual(observer.get("/api/v1/telemetry/state").status_code, 200)
        with observer.websocket_connect("/api/v1/telemetry/ws", headers={"Origin": ORIGIN}) as ws:
            self.assertEqual(ws.receive_json()["type"], "simulation_status")
        for path in ("start", "reduce-processing-load", "reset"):
            self.assertEqual(observer.post(f"/api/v1/virtual-device/{path}", headers=self.headers(obs_csrf)).status_code, 403)
        self.assertEqual(observer.get("/api/v1/virtual-device").status_code, 403)
        self.assertEqual(operator.get("/api/v1/telemetry/state").status_code, 403)

        analyst, analyst_csrf = self.client_for("analyst")
        self.assertEqual(analyst.get("/api/v1/telemetry/state").status_code, 200)
        self.assertEqual(analyst.post("/api/v1/virtual-device/pause", headers=self.headers(analyst_csrf)).status_code, 403)
        self.assertEqual(operator.post("/api/v1/virtual-device/pause", headers=self.headers(op_csrf)).status_code, 200)
        self.assertEqual(operator.post("/api/v1/virtual-device/resume", headers=self.headers(op_csrf)).status_code, 200)
        self.assertEqual(operator.post("/api/v1/virtual-device/reduce-processing-load", headers=self.headers(op_csrf)).status_code, 200)
        self.assertEqual(operator.post("/api/v1/virtual-device/end", headers=self.headers(op_csrf)).status_code, 200)
        with Session(self.engine) as db:
            self.assertGreaterEqual(db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.reason_code == "ROLE_DENIED")), 4)

        self.assertEqual(observer.post("/api/v1/auth/logout", headers=self.headers(obs_csrf)).status_code, 204)
        self.assertEqual(observer.get("/api/v1/auth/me").status_code, 401)
        with self.assertRaises(WebSocketDisconnect):
            with observer.websocket_connect("/api/v1/telemetry/ws", headers={"Origin": ORIGIN}):
                pass

    def test_invalid_packet_incident_analyst_decision_and_audit(self):
        operator, op_csrf = self.client_for("operator")
        analyst, analyst_csrf = self.client_for("analyst")
        observer, obs_csrf = self.client_for("observer")
        started = operator.post("/api/v1/virtual-device/start", headers=self.headers(op_csrf),
                                json={"scenario": "INVALID_TELEMETRY"})
        run_id = started.json()["run_id"]
        self.clock.advance(12)
        asyncio.run(self.telemetry.tick())
        state = analyst.get("/api/v1/telemetry/state").json()
        self.assertEqual([(item["sequence_number"], item["reason_code"]) for item in state["rejections"]],
                         [(10, "SCHEMA_REJECTED")])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample).where(
                TelemetrySample.run_id == run_id, TelemetrySample.sequence_number == 10)), 0)
        overview = analyst.get("/api/v1/security/overview").json()
        incident = next(item for item in overview["incidents"] if item["run_id"] == run_id)
        incident_id = incident["incident_id"]
        self.assertEqual(incident["reason_code"], "SCHEMA_REJECTED")
        self.assertEqual(observer.post(f"/api/v1/security/incidents/{incident_id}/close",
                                       headers=self.headers(obs_csrf), json={"reason": "Reviewed local test"}).status_code, 403)
        self.assertEqual(operator.post(f"/api/v1/security/incidents/{incident_id}/close",
                                       headers=self.headers(op_csrf), json={"reason": "Reviewed local test"}).status_code, 403)
        note = analyst.post(f"/api/v1/security/incidents/{incident_id}/notes", headers=self.headers(analyst_csrf),
                            json={"body": "Sintetik format rəddi təsdiqləndi."})
        self.assertEqual(note.status_code, 201, note.text)
        self.assertEqual(note.json()["author_username"], "analyst")
        self.assertEqual(analyst.post(f"/api/v1/security/incidents/{incident_id}/close",
                                      headers=self.headers(analyst_csrf), json={"reason": "Sintetik test paketi araşdırıldı."}).status_code, 200)
        after = analyst.get("/api/v1/security/overview").json()
        closed = next(item for item in after["incidents"] if item["incident_id"] == incident_id)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["notes"][0]["author_username"], "analyst")
        self.assertTrue(any(item["reason_code"] == "ROLE_DENIED" for item in after["audit"]))
        self.assertTrue(any(item["reason_code"] == "SCHEMA_REJECTED" for item in after["audit"]))

    def test_hmac_integrity_replay_and_rate_limit(self):
        operator, op_csrf = self.client_for("operator")
        started = operator.post("/api/v1/virtual-device/start", headers=self.headers(op_csrf)).json()
        run_id = started["run_id"]
        self.clock.advance(31)
        asyncio.run(self.telemetry.tick())
        with Session(self.engine) as db:
            before = db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == run_id))
        self.clock.advance(1)
        self.device.snapshot()
        valid = self.device.drain_signed_samples(KEY)[0]
        altered = valid.snapshot.model_copy(update={"sensors": valid.snapshot.sensors.model_copy(
            update={"temperature_1_c": 99.0})})
        self.telemetry._pending.append(SignedTelemetryPacket(altered, valid.source_id, valid.signature))
        asyncio.run(self.telemetry.tick())
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == run_id)), before)
        self.telemetry._pending.append(valid)
        asyncio.run(self.telemetry.tick())
        self.telemetry._pending.append(valid)
        asyncio.run(self.telemetry.tick())
        self.telemetry._pending.append(SignedTelemetryPacket(valid.snapshot, "unknown-test-source", valid.signature))
        asyncio.run(self.telemetry.tick())
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == run_id)), before + 1)
            codes = list(db.scalars(select(RejectedTelemetry.reason_code).where(RejectedTelemetry.run_id == run_id)))
            self.assertEqual(codes, ["INTEGRITY_REJECTED", "REPLAY_REJECTED", "SOURCE_REJECTED"])
            incident_codes = list(db.scalars(select(SecurityIncident.reason_code).where(SecurityIncident.run_id == run_id)))
            self.assertEqual(incident_codes, ["INTEGRITY_REJECTED", "REPLAY_REJECTED", "SOURCE_REJECTED"])
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.reason_code == "REPLAY_REJECTED")), 1)

        unknown = TestClient(self.app)
        self.clients.append(unknown)
        for _ in range(5):
            self.assertEqual(unknown.post("/api/v1/auth/login", headers={"Origin": ORIGIN},
                                          json={"username": "observer", "password": secrets.token_urlsafe(18)}).status_code, 401)
        self.assertEqual(unknown.post("/api/v1/auth/login", headers={"Origin": ORIGIN},
                                      json={"username": "observer", "password": secrets.token_urlsafe(18)}).status_code, 429)
        with Session(self.engine) as db:
            user = db.scalar(select(User).where(User.username == "operator"))
            self.assertNotEqual(user.password_hash, self.passwords["operator"])
            self.assertNotIn(self.passwords["operator"], user.password_hash)

    def test_three_run_reports_are_isolated_persisted_and_protected(self):
        anonymous = TestClient(self.app)
        self.clients.append(anonymous)
        self.assertEqual(anonymous.get("/api/v1/reports/runs").status_code, 401)
        operator, csrf = self.client_for("operator")
        analyst, analyst_csrf = self.client_for("analyst")
        results = {}
        for scenario, seconds in (("NORMAL_MISSION", 25), ("TEMPERATURE_ANOMALY", 30),
                                  ("INVALID_TELEMETRY", 12)):
            start = operator.post("/api/v1/virtual-device/start", headers=self.headers(csrf),
                                  json={"scenario": scenario})
            self.assertEqual(start.status_code, 200, start.text)
            run_id = start.json()["run_id"]
            self.clock.advance(seconds)
            asyncio.run(self.telemetry.tick())
            if scenario == "TEMPERATURE_ANOMALY":
                self.assertEqual(operator.post("/api/v1/virtual-device/reduce-processing-load",
                                               headers=self.headers(csrf)).status_code, 200)
            self.assertEqual(operator.post("/api/v1/virtual-device/end", headers=self.headers(csrf)).status_code, 200)
            self.assertEqual(operator.get(f"/api/v1/reports/runs/{run_id}").status_code, 403)
            preview = analyst.get(f"/api/v1/reports/runs/{run_id}")
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertIsNone(preview.json()["generated_at"])
            self.assertEqual(analyst.post(f"/api/v1/reports/runs/{run_id}/generate").status_code, 403)
            self.assertEqual(analyst.post(f"/api/v1/reports/runs/{run_id}/generate",
                                           headers=self.headers(analyst_csrf)).status_code, 200)
            report = analyst.get(f"/api/v1/reports/runs/{run_id}").json()
            self.assertEqual(report["run_id"], run_id)
            self.assertEqual(report["scenario"], scenario)
            self.assertEqual(report["status"], "ENDED")
            self.assertIsNotNone(report["generated_at"])
            with Session(self.engine) as db:
                self.assertEqual(report["accepted_count"], db.scalar(select(func.count()).select_from(TelemetrySample)
                    .where(TelemetrySample.run_id == run_id)))
            results[scenario] = report
        self.assertEqual(len({item["run_id"] for item in results.values()}), 3)
        self.assertEqual(results["NORMAL_MISSION"]["rejected_count"], 0)
        self.assertTrue(results["TEMPERATURE_ANOMALY"]["rule_alerts"])
        self.assertTrue(any(item["action"] == "reduce_processing_load" for item in
                            results["TEMPERATURE_ANOMALY"]["operator_events"]))
        invalid = results["INVALID_TELEMETRY"]
        self.assertEqual(invalid["accepted_count"], 11)
        self.assertEqual(invalid["rejected_count"], 1)
        self.assertEqual(invalid["sequence_gaps"], 1)
        self.assertEqual(invalid["rejection_reasons"], ["SCHEMA_REJECTED"])
        self.assertEqual(invalid["latest_sample"]["sequence_number"], 12)
        self.assertEqual(invalid["security_incidents"][0]["reason_code"], "SCHEMA_REJECTED")
        observer, _ = self.client_for("observer")
        self.assertEqual(observer.get(f"/api/v1/reports/runs/{invalid['run_id']}").json()["generated_at"],
                         invalid["generated_at"])


if __name__ == "__main__":
    unittest.main()
