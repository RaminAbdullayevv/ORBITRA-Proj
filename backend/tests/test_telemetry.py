import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, TelemetrySample
from app.integrity import sign_packet
from app.simulator import DeviceStatus, VirtualSpacecraftSimulator
from app.telemetry import TelemetryCoordinator, TelemetryStore

TEST_KEY = b"orbitra-test-integrity-key-32byte!"


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += seconds


class TelemetryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = FakeClock()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.device = VirtualSpacecraftSimulator(clock=self.clock)
        self.store = TelemetryStore(self.engine, TEST_KEY)
        self.service = TelemetryCoordinator(self.device, self.store)

    async def asyncTearDown(self):
        self.engine.dispose()

    def sample_count(self) -> int:
        with Session(self.engine) as db:
            return db.scalar(select(func.count()).select_from(TelemetrySample)) or 0

    async def test_start_pause_resume_reset_and_unique_samples(self):
        started = await self.service.command("start")
        run_id = started.run_id
        self.assertIsNotNone(run_id)
        self.clock.advance(5.2)
        await self.service.tick()
        history = await self.service.history(run_id, None, 300)
        self.assertEqual([item.sequence_number for item in history.samples], [1, 2, 3, 4, 5])
        self.assertEqual(self.sample_count(), 5)

        # A repeated signed packet is rejected without another accepted row.
        duplicate, _, rejected = self.store.process_sample(sign_packet(self.device.snapshot(), TEST_KEY))
        self.assertIsNone(duplicate)
        self.assertEqual(rejected.reason_code, "REPLAY_REJECTED")
        self.assertEqual(self.sample_count(), 5)

        paused = await self.service.command("pause")
        self.assertEqual(paused.status, DeviceStatus.PAUSED)
        self.clock.advance(12)
        still_paused = await self.service.tick()
        self.assertEqual(still_paused.simulation_elapsed_seconds, 5)
        self.assertEqual(still_paused.sensors, paused.sensors)
        self.assertEqual(self.sample_count(), 5)

        resumed = await self.service.command("resume")
        self.assertEqual(resumed.run_id, run_id)
        self.clock.advance(3.2)
        await self.service.tick()
        self.assertEqual(self.sample_count(), 8)
        gap = await self.service.history(run_id, 5, 100)
        self.assertEqual([item.sequence_number for item in gap.samples], [6, 7, 8])

        reset = await self.service.command("reset")
        self.assertEqual(reset.status, DeviceStatus.IDLE)
        self.assertEqual(reset.simulation_elapsed_seconds, 0)
        self.assertEqual(self.sample_count(), 8)
        old_run = await self.service.state(run_id)
        self.assertEqual(old_run.run.last_status, "RESET")
        self.assertEqual(old_run.latest_sample.sequence_number, 8)

        new_run = await self.service.command("start")
        self.assertNotEqual(new_run.run_id, run_id)
        self.assertEqual((await self.service.history(new_run.run_id, None, 300)).samples, [])
        self.assertEqual(self.sample_count(), 8)


if __name__ == "__main__":
    unittest.main()
