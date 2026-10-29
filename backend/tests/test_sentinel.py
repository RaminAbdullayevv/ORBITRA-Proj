"""Sentinel security boundary, attribution, roles and persisted reporting."""

import unittest
import secrets
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.auth as auth_module
import app.api.auth_routes as auth_routes
import app.api.security_routes as security_routes
import app.api.sentinel_routes as sentinel_routes
import app.api.simulator_routes as simulator_routes
from app.auth import SecurityService
from app.integrity import sign_packet
from app.models import (Base, RejectedTelemetry, RunAnalysis, SecurityIncident, TelemetrySample,
                        TrustAssessment, User)
from app.reports import read_report
from app.simulator import ScenarioName, VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore


KEY = b"sentinel-unit-test-signature-key-32"
ORIGIN = "http://localhost:5173"


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class SentinelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.clock = Clock()
        self.device = VirtualSpacecraftSimulator(clock=self.clock)
        self.store = TelemetryStore(self.engine, KEY)
        self.service = TelemetryCoordinator(self.device, self.store)

    async def asyncTearDown(self):
        self.engine.dispose()

    def count(self, model, run_id):
        field = model.mission_id if model is TrustAssessment else model.run_id
        with Session(self.engine) as db:
            return db.scalar(select(func.count()).select_from(model).where(field == run_id)) or 0

    async def start_and_tick(self, scenario, seconds):
        run = await self.service.command("start", scenario)
        self.clock.advance(seconds)
        await self.service.tick()
        return run.run_id

    async def test_admin_login_permissions_and_session_lifecycle(self):
        auth = SecurityService(self.engine)
        admin_password = secrets.token_urlsafe(18)
        auth.create_if_missing("admin", admin_password, "ADMIN")
        with Session(self.engine) as db:
            seeded = db.scalar(select(User).where(User.username == "admin"))
            first_hash = seeded.password_hash
            self.assertNotEqual(first_hash, admin_password)
            self.assertEqual(seeded.role, "ADMIN")
        auth.create_if_missing("admin", secrets.token_urlsafe(18), "ADMIN")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(User.password_hash).where(User.username == "admin")), first_hash)
        app = FastAPI()
        for router in (auth_routes.router, simulator_routes.router, security_routes.router, sentinel_routes.router):
            app.include_router(router)
        with ExitStack() as patches:
            patches.enter_context(patch.object(auth_module, "security", auth))
            patches.enter_context(patch.object(auth_routes, "security", auth))
            patches.enter_context(patch.object(security_routes, "security", auth))
            patches.enter_context(patch.object(simulator_routes, "telemetry", self.service))
            patches.enter_context(patch.object(sentinel_routes, "telemetry", self.service))
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/v1/sentinel/overview").status_code, 401)
                self.assertEqual(client.get("/api/v1/virtual-device").status_code, 401)
                bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"},
                                  headers={"Origin": ORIGIN})
                self.assertEqual(bad.status_code, 401)
                good = client.post("/api/v1/auth/login", json={"username": "admin", "password": admin_password},
                                   headers={"Origin": ORIGIN})
                self.assertEqual(good.status_code, 200, good.text)
                self.assertEqual(good.json()["role"], "ADMIN")
                self.assertEqual(client.get("/api/v1/auth/me").json()["username"], "admin")
                headers = {"Origin": ORIGIN, "X-CSRF-Token": good.json()["csrf_token"]}
                started = client.post("/api/v1/virtual-device/start", headers=headers,
                                      json={"scenario": "NORMAL_MISSION"})
                self.assertEqual(started.status_code, 403, started.text)
                self.assertEqual(client.get("/api/v1/sentinel/overview").status_code, 200)
                started_run = await self.service.command("start", ScenarioName.NORMAL_MISSION)
                self.clock.advance(1)
                await self.service.tick()
                run_id = started_run.run_id
                latest_id = self.store.read_trust_overview(run_id)["latest"]["id"]
                decision_url = f"/api/v1/sentinel/runs/{run_id}/decisions/{latest_id}"
                self.assertEqual(client.get(decision_url).json()["id"], latest_id)
                self.assertEqual(client.get(f"/api/v1/sentinel/runs/another-run/decisions/{latest_id}").status_code, 404)
                self.assertEqual(client.post("/api/v1/auth/logout", headers=headers).status_code, 204)
                self.assertEqual(client.get("/api/v1/auth/me").status_code, 401)
                self.assertEqual(client.get(decision_url).status_code, 401)

    async def test_valid_packet_and_ordered_security_rejections(self):
        run_id = await self.start_and_tick(ScenarioName.NORMAL_MISSION, 1)
        self.assertEqual(self.count(TelemetrySample, run_id), 1)
        self.assertEqual(self.store.read_trust_overview(run_id)["stats"]["accepted"], 1)
        sample = self.device.snapshot().model_copy(update={"simulation_elapsed_seconds": 2,
                                                        "updated_at": datetime.now(timezone.utc)})
        packets = [
            (replace(sign_packet(sample, KEY), signature="0" * 64), "INTEGRITY_REJECTED"),
            (sign_packet(sample, KEY, "unregistered-device"), "SOURCE_REJECTED"),
            (sign_packet(sample.model_copy(update={"updated_at": datetime.now(timezone.utc) - timedelta(seconds=30)}), KEY), "STALE_REJECTED"),
            (sign_packet(sample.model_copy(update={"simulation_elapsed_seconds": 3,
                "updated_at": datetime.now(timezone.utc) + timedelta(seconds=30)}), KEY), "STALE_REJECTED"),
            (sign_packet(self.device.snapshot(), KEY), "REPLAY_REJECTED"),
        ]
        for packet, reason in packets:
            accepted, _, rejected = self.store.process_sample(packet)
            self.assertIsNone(accepted)
            self.assertEqual(rejected.reason_code, reason)
        self.assertEqual(self.count(TelemetrySample, run_id), 1)
        self.assertEqual(self.count(TrustAssessment, run_id), 6)
        self.assertEqual(self.count(SecurityIncident, run_id), 5)
        self.assertEqual(self.store.read_trust_overview(run_id)["stats"]["quarantined"], 5)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(RunAnalysis)), 0)
            self.assertTrue(all(row.raw_payload_json for row in db.scalars(select(RejectedTelemetry))))
        self.clock.advance(1)
        await self.service.tick()
        self.assertEqual(self.count(TelemetrySample, run_id), 2)

    async def test_rejected_packet_never_enters_ai_or_live_sample_stream(self):
        run_id = await self.start_and_tick(ScenarioName.INVALID_SIGNATURE, 12)
        samples = (await self.service.history(run_id, None, 300)).samples
        self.assertNotIn(10, [item.sequence_number for item in samples])
        overview = self.store.read_trust_overview(run_id)
        self.assertEqual(overview["stats"]["integrity_incident"], 1)
        self.assertEqual(overview["stats"]["quarantined"], 1)
        self.assertEqual(overview["quarantine"][0]["reason_code"], "INTEGRITY_REJECTED")
        self.assertEqual(overview["active_integrity_count"], 1)
        assessment = self.store.read_trust_decision(run_id, overview["active_integrity_assessment_id"])
        self.assertEqual(assessment["final_verdict"], "INTEGRITY INCIDENT")
        self.assertEqual(overview["status"], "DEGRADED")
        self.assertEqual(self.service.ai.status(run_id).latest_sequence_number, None)

    async def test_system_anomaly_and_sensor_fault_are_distinct(self):
        hot = await self.start_and_tick(ScenarioName.TEMPERATURE_ANOMALY, 24)
        hot_count = self.store.read_trust_overview(hot)["stats"]["system_anomaly"]
        self.assertGreater(hot_count, 0)
        self.assertEqual(len(read_report(self.engine, hot)["telemetry_trust"]["key_decisions"]), hot_count)
        await self.service.command("reset")
        faulty = await self.start_and_tick(ScenarioName.SINGLE_SENSOR_FAULT, 17)
        overview = self.store.read_trust_overview(faulty)
        self.assertGreater(overview["stats"]["sensor_fault"], 0)
        report = read_report(self.engine, faulty)
        self.assertEqual(report["subsystems"]["thermal"], "NORMAL")
        self.assertEqual(report["telemetry_trust"]["sensor_fault"], overview["stats"]["sensor_fault"])
        self.assertEqual(report["telemetry_trust"]["system_anomaly"], 0)
        self.assertEqual(read_report(self.engine, hot)["telemetry_trust"]["sensor_fault"], 0)

    async def test_replay_scenario_reset_isolation_and_determinism(self):
        first = await self.start_and_tick(ScenarioName.REPLAYED_TELEMETRY, 13)
        rows = (await self.service.history(first, None, 300)).samples
        self.assertEqual([item.sequence_number for item in rows], [*range(1, 10), 11, 12, 13])
        self.assertEqual(self.store.read_trust_overview(first)["stats"]["replay_incident"], 1)
        first_values = [item.sensors.temperature_1_c for item in rows]
        await self.service.command("reset")
        self.assertIsNone((await self.service.state()).run)
        second = await self.start_and_tick(ScenarioName.REPLAYED_TELEMETRY, 13)
        self.assertNotEqual(first, second)
        second_rows = (await self.service.history(second, None, 300)).samples
        self.assertEqual(first_values, [item.sensors.temperature_1_c for item in second_rows])
        self.assertEqual(self.store.read_trust_overview(second)["stats"]["replay_incident"], 1)
        self.assertEqual(self.store.read_trust_decisions(second, None, 5)["decisions"][0]["mission_id"], second)

    async def test_report_quarantine_counts_and_operator_response(self):
        run_id = await self.start_and_tick(ScenarioName.INVALID_SIGNATURE, 11)
        await self.service.command("reduce_processing_load")
        await self.service.command("end")
        report = read_report(self.engine, run_id)
        self.assertEqual(report["telemetry_trust"]["accepted"], 10)
        self.assertEqual(report["telemetry_trust"]["quarantined"], 1)
        self.assertEqual(report["telemetry_trust"]["integrity_incident"], 1)
        self.assertEqual(report["telemetry_trust"]["final_status"], "DEGRADED")
        self.assertEqual(report["telemetry_trust"]["key_decisions"][0]["verdict"], "INTEGRITY INCIDENT")
        self.assertTrue(any(item["action"] == "reduce_processing_load" for item in report["operator_events"]))
        self.assertEqual(report["telemetry_trust"]["ruleset_version"], "sentinel-teaching-v1")


if __name__ == "__main__":
    unittest.main()
