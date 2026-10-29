import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai_analysis import AIAnalyzer, METADATA_FILE, MODEL_FILE
from app.integrity import sign_packet
from app.models import AIEvent, Base, RejectedTelemetry, TelemetrySample
from app.simulator import ScenarioName, VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore

TEST_KEY = b"orbitra-test-integrity-key-32byte!"


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class AIAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.device = VirtualSpacecraftSimulator(clock=self.clock, seed=1001)
        self.service = TelemetryCoordinator(self.device, TelemetryStore(self.engine, TEST_KEY))
        self.socket = FakeSocket()
        self.service._clients.add(self.socket)

    async def asyncTearDown(self):
        self.engine.dispose()

    async def test_temperature_anomaly_is_one_persisted_observational_event(self):
        started = await self.service.command("start", ScenarioName.TEMPERATURE_ANOMALY)
        self.clock.advance(35)
        await self.service.tick()
        state = await self.service.state()
        self.assertEqual(state.ai_status.model_status, "READY")
        self.assertEqual(state.ai_status.model_version, "iforest-normal-v1")
        self.assertEqual(len(state.ai_events), 1)
        event = state.ai_events[0]
        self.assertEqual(event.status, "ACTIVE")
        self.assertGreaterEqual(event.start_sequence_number, 20)
        self.assertGreater(event.score, state.ai_status.threshold)
        self.assertIn("temperature_1_c", event.affected_sensors)
        self.assertIn("Müşahidə olunan dəyişikliklər", event.explanation)
        self.assertTrue(event.baseline_comparison)
        self.assertEqual(len({item["event_id"] for item in self.socket.messages if item["type"] == "ai_event"}), 1)

        before_pause = state.ai_status.latest_sequence_number
        await self.service.command("pause")
        self.clock.advance(10)
        await self.service.tick()
        self.assertEqual((await self.service.state()).ai_status.latest_sequence_number, before_pause)
        await self.service.command("resume")
        await self.service.command("reduce_processing_load")
        self.clock.advance(55)
        await self.service.tick()
        later = await self.service.state()
        self.assertGreater(later.ai_status.latest_sequence_number, before_pause)
        self.assertEqual(len(later.ai_events), 1)
        self.assertEqual(later.ai_events[0].event_id, event.event_id)
        self.assertIsNotNone(later.ai_events[0].ended_at)
        self.assertEqual(later.ai_events[0].status, "RESOLVED")
        actions = [item["action"] for item in self.socket.messages if item["type"] == "operator_event"]
        self.assertEqual(actions.count("reduce_processing_load"), 1)

        reloaded = AIAnalyzer(self.engine)
        reloaded.initialize()
        self.assertEqual(reloaded.read_events(started.run_id)[0].event_id, event.event_id)

    async def test_rejected_packet_never_enters_ai_window_or_event(self):
        self.device._base_seed = 24092026
        started = await self.service.command("start", ScenarioName.INVALID_TELEMETRY)
        self.clock.advance(35)
        await self.service.tick()
        state = await self.service.state()
        self.assertEqual([item.sequence_number for item in state.rejections], [10])
        self.assertEqual(state.ai_status.latest_sequence_number, 35)
        self.assertEqual(len(state.ai_events), 0)
        assessments = [message for message in self.socket.messages if message["type"] == "ai_assessment"]
        self.assertNotIn(10, [message["ai_status"]["latest_sequence_number"] for message in assessments])
        self.assertEqual(min(message["ai_status"]["latest_sequence_number"] for message in assessments if message["ai_status"]["latest_sequence_number"] is not None), 30)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == started.run_id, TelemetrySample.sequence_number == 10)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(RejectedTelemetry).where(RejectedTelemetry.run_id == started.run_id)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AIEvent).where(AIEvent.run_id == started.run_id)), 0)

    async def test_missing_model_does_not_stop_accepted_telemetry(self):
        with patch("app.ai_analysis.MODEL_FILE", Path("missing-model.joblib")), patch("app.ai_analysis.METADATA_FILE", Path("missing-metadata.json")):
            started = await self.service.command("start", ScenarioName.NORMAL_MISSION)
            self.clock.advance(25)
            await self.service.tick()
            state = await self.service.state()
            self.assertEqual(state.ai_status.model_status, "NOT_TRAINED")
            self.assertEqual(state.ai_events, [])
            self.assertEqual(len((await self.service.history(started.run_id, None, 300)).samples), 25)

    async def test_high_packet_loss_is_rule_alert_not_ai_source(self):
        started = await self.service.command("start", ScenarioName.NORMAL_MISSION)
        self.clock.advance(1)
        sample = self.device.snapshot()
        high = sample.model_copy(update={"sensors": sample.sensors.model_copy(update={"packet_loss_percent": 0.7})})
        _, alerts, _ = self.service.store.process_sample(sign_packet(high, TEST_KEY))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].metric_key, "packet_loss_percent")
        self.clock.advance(1)
        sample2 = self.device.snapshot()
        low = sample2.model_copy(update={"sensors": sample2.sensors.model_copy(update={"packet_loss_percent": 0.2})})
        _, resolved, _ = self.service.store.process_sample(sign_packet(low, TEST_KEY))
        self.assertEqual(resolved[0].status, "RESOLVED")
        self.assertEqual(self.service.ai.read_events(started.run_id), [])


class TrainedArtifactTests(unittest.TestCase):
    def test_model_provenance_and_holdout_are_separate(self):
        metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        report = json.loads((METADATA_FILE.parent / "training_report.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest(), metadata["model_sha256"])
        self.assertEqual(metadata["window_seconds"], 20)
        groups = [set(metadata[key]) for key in ("training_seeds", "calibration_seeds", "test_normal_seeds", "test_anomaly_seeds")]
        self.assertEqual(sum(len(group) for group in groups), len(set().union(*groups)))
        self.assertEqual(report["true_synthetic_events"], len(metadata["test_anomaly_seeds"]))
        self.assertEqual(report["missed_synthetic_events"] + report["detected_synthetic_events"], report["true_synthetic_events"])


if __name__ == "__main__":
    unittest.main()
