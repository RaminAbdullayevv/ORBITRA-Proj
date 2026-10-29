import unittest

from app.simulator import (
    INITIAL_SENSORS,
    DeviceStatus,
    InvalidTransition,
    VirtualSpacecraftSimulator,
)


class FakeClock:
    def __init__(self):
        self.seconds = 100.0

    def __call__(self):
        return self.seconds

    def advance(self, seconds: float):
        self.seconds += seconds


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.simulator = VirtualSpacecraftSimulator(clock=self.clock)

    def test_start_pause_resume_reset_and_reproducibility(self):
        idle = self.simulator.snapshot()
        self.assertEqual(idle.status, DeviceStatus.IDLE)
        self.assertEqual(idle.simulation_elapsed_seconds, 0)
        self.assertIsNone(idle.run_id)
        self.assertEqual(idle.sensors, INITIAL_SENSORS)

        started = self.simulator.start()
        self.assertEqual(started.status, DeviceStatus.RUNNING)
        self.assertIsNotNone(started.run_id)
        with self.assertRaises(InvalidTransition):
            self.simulator.start()

        self.clock.advance(5.4)
        moving = self.simulator.snapshot()
        self.assertEqual(moving.simulation_elapsed_seconds, 5)
        self.assertLess(moving.sensors.battery_level_percent, idle.sensors.battery_level_percent)
        self.assertNotEqual(moving.sensors.cpu_load_percent, idle.sensors.cpu_load_percent)

        paused = self.simulator.pause()
        self.clock.advance(20)
        still_paused = self.simulator.snapshot()
        self.assertEqual(still_paused.status, DeviceStatus.PAUSED)
        self.assertEqual(still_paused.simulation_elapsed_seconds, paused.simulation_elapsed_seconds)
        self.assertEqual(still_paused.sensors, paused.sensors)
        with self.assertRaises(InvalidTransition):
            self.simulator.pause()

        resumed = self.simulator.resume()
        self.assertEqual(resumed.run_id, started.run_id)
        self.clock.advance(3)
        moving_again = self.simulator.snapshot()
        self.assertEqual(moving_again.simulation_elapsed_seconds, 8)
        self.assertNotEqual(moving_again.sensors, paused.sensors)

        reset = self.simulator.reset()
        self.assertEqual(reset.status, DeviceStatus.IDLE)
        self.assertEqual(reset.simulation_elapsed_seconds, 0)
        self.assertEqual(reset.sensors, INITIAL_SENSORS)
        self.assertIsNone(reset.run_id)

        self.simulator.start()
        self.clock.advance(5.4)
        self.assertEqual(self.simulator.snapshot().sensors, moving.sensors)

    def test_invalid_transitions_and_bounded_gradual_readings(self):
        with self.assertRaises(InvalidTransition):
            self.simulator.pause()
        with self.assertRaises(InvalidTransition):
            self.simulator.resume()

        self.simulator.start()
        previous = self.simulator.snapshot().sensors
        for _ in range(120):
            self.clock.advance(1)
            sensors = self.simulator.snapshot().sensors
            self.assertGreaterEqual(sensors.battery_level_percent, 0)
            self.assertLessEqual(sensors.battery_level_percent, 100)
            self.assertGreaterEqual(sensors.cpu_load_percent, 18)
            self.assertLessEqual(sensors.cpu_load_percent, 44)
            self.assertGreaterEqual(sensors.signal_strength_percent, 76)
            self.assertLessEqual(sensors.signal_strength_percent, 95)
            self.assertLess(abs(sensors.temperature_1_c - previous.temperature_1_c), 0.5)
            self.assertLess(abs(sensors.temperature_2_c - previous.temperature_2_c), 0.5)
            self.assertLess(abs(sensors.temperature_3_c - previous.temperature_3_c), 0.5)
            previous = sensors

        self.simulator.pause()
        with self.assertRaises(InvalidTransition):
            self.simulator.start()
        self.simulator.reset()
        self.assertEqual(self.simulator.reset().sensors, INITIAL_SENSORS)


if __name__ == "__main__":
    unittest.main()
