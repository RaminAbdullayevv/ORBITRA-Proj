import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, RejectedTelemetry, RuleAlert, SimulationRun, TelemetrySample
from app.integrity import sign_packet
from app.simulator import INITIAL_SENSORS, ScenarioName, VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore

TEST_KEY = b"orbitra-test-integrity-key-32byte!"


class FakeClock:
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


class ScenarioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = FakeClock()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.service = TelemetryCoordinator(VirtualSpacecraftSimulator(clock=self.clock), TelemetryStore(self.engine, TEST_KEY))
        self.socket = FakeSocket()
        self.service._clients.add(self.socket)

    async def asyncTearDown(self):
        self.engine.dispose()

    async def test_normal_is_reproducible_and_keeps_events_separate(self):
        first = await self.service.command("start", ScenarioName.NORMAL_MISSION)
        self.clock.advance(25)
        await self.service.tick()
        samples = (await self.service.history(first.run_id, None, 300)).samples
        self.assertEqual(len(samples), 25)
        self.assertEqual((await self.service.state()).active_alerts, [])
        self.assertEqual((await self.service.state()).rejections, [])
        self.assertTrue(all(s.sensors.cpu_load_percent <= 40 and s.sensors.temperature_1_c < 24.5 for s in samples))
        await self.service.command("end")
        again = await self.service.command("start", ScenarioName.NORMAL_MISSION)
        self.assertNotEqual(first.run_id, again.run_id)
        self.clock.advance(25)
        await self.service.tick()
        repeated = (await self.service.history(again.run_id, None, 300)).samples
        self.assertEqual([s.sensors for s in samples], [s.sensors for s in repeated])
        with Session(self.engine) as db:
            self.assertEqual(db.get(SimulationRun, first.run_id).scenario, "NORMAL_MISSION")
            self.assertEqual(db.get(SimulationRun, again.run_id).scenario, "NORMAL_MISSION")

    async def test_temperature_rule_follows_load_and_resolves_after_reduction(self):
        started = await self.service.command("start", ScenarioName.TEMPERATURE_ANOMALY)
        self.clock.advance(24)
        await self.service.tick()
        samples = (await self.service.history(started.run_id, None, 300)).samples
        self.assertGreater(samples[12].sensors.cpu_load_percent, samples[3].sensors.cpu_load_percent)
        self.assertGreater(samples[12].sensors.current_a, samples[3].sensors.current_a)
        self.assertGreater(samples[20].sensors.temperature_1_c, samples[10].sensors.temperature_1_c)
        opened = (await self.service.state()).active_alerts
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].metric_key, "temperature_1_c")
        before = samples[-1].sensors
        await self.service.command("reduce_processing_load")
        self.clock.advance(1)
        await self.service.tick()
        first_after = (await self.service.history(started.run_id, 24, 1)).samples[0].sensors
        self.assertLess(first_after.cpu_load_percent, before.cpu_load_percent)
        self.assertGreater(first_after.temperature_1_c, INITIAL_SENSORS.temperature_1_c)
        self.clock.advance(25)
        await self.service.tick()
        state = await self.service.state()
        self.assertEqual(state.active_alerts, [])
        self.assertEqual(state.rule_alerts[0].status, "RESOLVED")
        self.assertIsNotNone(state.rule_alerts[0].closed_at)
        self.assertEqual(len([m for m in self.socket.messages if m["type"] == "rule_alert"]), 2)

    async def test_invalid_packet_is_only_rejection_and_stream_continues(self):
        started = await self.service.command("start", ScenarioName.INVALID_TELEMETRY)
        self.clock.advance(13)
        await self.service.tick()
        samples = (await self.service.history(started.run_id, None, 300)).samples
        self.assertEqual([s.sequence_number for s in samples], [*range(1, 10), 11, 12, 13])
        self.assertNotIn(10, [m["sequence_number"] for m in self.socket.messages if m["type"] == "telemetry_sample"])
        rejections = (await self.service.state()).rejections
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0].sequence_number, 10)
        self.assertIn("schema_version", rejections[0].reason)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == started.run_id, TelemetrySample.sequence_number == 10)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(RejectedTelemetry).where(RejectedTelemetry.run_id == started.run_id)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(RuleAlert).where(RuleAlert.run_id == started.run_id)), 0)
        self.assertEqual(len([m for m in self.socket.messages if m["type"] == "telemetry_rejected"]), 1)
        duplicate = self.service.device.snapshot().model_copy(update={
            "schema_version": "9.9-test", "simulation_elapsed_seconds": 10,
        })
        _, _, second_rejection = self.service.store.process_sample(sign_packet(duplicate, TEST_KEY))
        self.assertEqual(second_rejection.reason_code, "SCHEMA_REJECTED")
        await self.service.command("reset")
        self.assertEqual((await self.service.state()).rejections, [])
        next_run = await self.service.command("start", ScenarioName.NORMAL_MISSION)
        self.assertNotEqual(next_run.run_id, started.run_id)
        self.assertEqual((await self.service.state()).rejections, [])
        self.assertEqual(len((await self.service.state(started.run_id)).rejections), 1)


if __name__ == "__main__":
    unittest.main()
