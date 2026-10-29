import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, OperatorEvent, SimulationRun, TelemetrySample
from app.simulator import DeviceStatus, InvalidTransition, VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore

TEST_KEY = b"orbitra-test-integrity-key-32byte!"


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class OperatorEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = FakeClock()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.service = TelemetryCoordinator(VirtualSpacecraftSimulator(clock=self.clock), TelemetryStore(self.engine, TEST_KEY))

    async def asyncTearDown(self):
        self.engine.dispose()

    async def test_end_prevents_resume_and_events_survive_new_run(self):
        started = await self.service.command("start")
        run_id = started.run_id
        self.clock.advance(6.2)
        await self.service.tick()
        paused = await self.service.command("pause")
        self.assertEqual(paused.status, DeviceStatus.PAUSED)
        resumed = await self.service.command("resume")
        self.assertEqual(resumed.run_id, run_id)
        ended = await self.service.command("end")
        self.assertEqual(ended.status, DeviceStatus.ENDED)
        elapsed = ended.simulation_elapsed_seconds
        self.clock.advance(12)
        self.assertEqual((await self.service.tick()).simulation_elapsed_seconds, elapsed)
        with self.assertRaises(InvalidTransition):
            await self.service.command("resume")
        with self.assertRaises(InvalidTransition):
            await self.service.command("end")
        first_events = (await self.service.event_history(run_id, 0, 100)).events
        self.assertEqual([event.action for event in first_events], ["start", "pause", "resume", "end", "resume", "end"])
        self.assertEqual([event.outcome for event in first_events], ["SUCCESS"] * 4 + ["REJECTED"] * 2)
        self.assertEqual(len({event.event_id for event in first_events}), 6)
        self.assertEqual([event.event_number for event in first_events], sorted(event.event_number for event in first_events))
        with Session(self.engine) as db:
            self.assertEqual(db.get(SimulationRun, run_id).last_status, "ENDED")
            self.assertEqual(db.scalar(select(func.count()).select_from(TelemetrySample)), elapsed)
        await self.service.command("reset")
        with Session(self.engine) as db:
            self.assertEqual(db.get(SimulationRun, run_id).last_status, "ENDED")
        new_run = await self.service.command("start")
        self.assertNotEqual(new_run.run_id, run_id)
        self.assertEqual([event.action for event in (await self.service.event_history(new_run.run_id, 0, 100)).events], ["start"])
        self.assertEqual(len((await self.service.event_history(run_id, 0, 100)).events), 7)

    async def test_reduce_load_is_bounded_and_duplicate_change_rejected(self):
        started = await self.service.command("start")
        run_id = started.run_id
        self.clock.advance(15)
        before = await self.service.tick()
        reduced = await self.service.command("reduce_processing_load")
        self.assertEqual(reduced.sensors, before.sensors)
        with self.assertRaises(InvalidTransition):
            await self.service.command("reduce_processing_load")
        self.clock.advance(1)
        first = await self.service.tick()
        self.assertLess(abs(first.sensors.temperature_1_c - before.sensors.temperature_1_c), 0.5)
        self.clock.advance(19)
        later = await self.service.tick()
        self.assertLess(later.sensors.cpu_load_percent, before.sensors.cpu_load_percent)
        self.assertLess(later.sensors.current_a, before.sensors.current_a)
        events = (await self.service.event_history(run_id, 0, 100)).events
        self.assertEqual([(event.action, event.outcome) for event in events], [
            ("start", "SUCCESS"), ("reduce_processing_load", "SUCCESS"),
            ("reduce_processing_load", "REJECTED"),
        ])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(OperatorEvent)), 3)


if __name__ == "__main__":
    unittest.main()
