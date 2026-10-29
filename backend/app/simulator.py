"""One local, in-memory educational spacecraft unit.

State advances using backend monotonic time. Each whole-second step is queued
for the telemetry layer; this module remains the only sensor model.
"""

import math
import random
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Callable
from uuid import uuid4

from pydantic import BaseModel


class DeviceStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ENDED = "ENDED"


class ScenarioName(str, Enum):
    NORMAL_MISSION = "NORMAL_MISSION"
    TEMPERATURE_ANOMALY = "TEMPERATURE_ANOMALY"
    INVALID_TELEMETRY = "INVALID_TELEMETRY"
    SINGLE_SENSOR_FAULT = "SINGLE_SENSOR_FAULT"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    REPLAYED_TELEMETRY = "REPLAYED_TELEMETRY"
    SPOOFED_TELEMETRY = "SPOOFED_TELEMETRY"


class SubsystemStatus(str, Enum):
    STANDBY = "STANDBY"
    NOMINAL = "NOMINAL"
    PAUSED = "PAUSED"


class SystemMode(str, Enum):
    STANDBY = "STANDBY"
    NOMINAL = "NOMINAL"
    HOLD = "HOLD"


class SensorReadings(BaseModel):
    battery_level_percent: float
    voltage_v: float
    current_a: float
    temperature_1_c: float
    temperature_2_c: float
    temperature_3_c: float
    cpu_load_percent: float
    memory_usage_percent: float
    signal_strength_percent: float
    communication_latency_ms: float
    packet_loss_percent: float


class SubsystemStatuses(BaseModel):
    power: SubsystemStatus
    thermal: SubsystemStatus
    communications: SubsystemStatus
    computer: SubsystemStatus


class SimulatorSnapshot(BaseModel):
    schema_version: str
    run_id: str | None
    scenario: ScenarioName | None
    status: DeviceStatus
    simulation_elapsed_seconds: int
    system_mode: SystemMode
    subsystem_statuses: SubsystemStatuses
    sensors: SensorReadings
    updated_at: datetime


class InvalidTransition(Exception):
    def __init__(self, action: str, status: DeviceStatus, reason: str | None = None):
        self.action = action
        self.status = status
        self.reason = reason or f"{status.value} vəziyyətində {action} əməliyyatı mümkün deyil."
        super().__init__(f"{action} cannot run while {status.value}")


INITIAL_SENSORS = SensorReadings(
    battery_level_percent=84.00,
    voltage_v=28.08,
    current_a=1.90,
    temperature_1_c=21.40,
    temperature_2_c=22.10,
    temperature_3_c=20.80,
    cpu_load_percent=28.00,
    memory_usage_percent=36.00,
    signal_strength_percent=87.00,
    communication_latency_ms=41.50,
    packet_loss_percent=0.10,
)


def _bounded(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


class VirtualSpacecraftSimulator:
    SEED = 24092026

    def __init__(self, clock: Callable[[], float] = time.monotonic, seed: int = SEED):
        self._clock = clock
        self._base_seed = seed
        self._lock = threading.RLock()
        self._reset_state()

    def _reset_state(self) -> None:
        self._status = DeviceStatus.IDLE
        self._run_id: str | None = None
        self._scenario: ScenarioName | None = None
        self._sensors = INITIAL_SENSORS.model_copy(deep=True)
        self._rng = random.Random(self._base_seed)
        self._elapsed_before = 0.0
        self._running_since: float | None = None
        self._last_step = 0
        self._sample_events: list[SimulatorSnapshot] = []
        self._load_reduced = False
        self._previous_signed_packet = None
        self._updated_at = datetime.now(timezone.utc)

    def _elapsed(self) -> float:
        if self._status == DeviceStatus.RUNNING and self._running_since is not None:
            return self._elapsed_before + max(0.0, self._clock() - self._running_since)
        return self._elapsed_before

    def _advance(self, elapsed: float) -> None:
        while self._last_step < math.floor(elapsed):
            self._step()
            self._last_step += 1
            self._updated_at = datetime.now(timezone.utc)
            sample = self._build_snapshot(self._last_step)
            if self._scenario == ScenarioName.INVALID_TELEMETRY and self._last_step == 10:
                sample = sample.model_copy(update={"schema_version": "9.9-test"})
            self._sample_events.append(sample)

    def _step(self) -> None:
        previous = self._sensors
        rng = self._rng

        anomaly = self._scenario == ScenarioName.TEMPERATURE_ANOMALY and self._last_step >= 7 and not self._load_reduced
        cpu_target = 20 if self._load_reduced else 43 if anomaly else 28
        cpu = _bounded(previous.cpu_load_percent + rng.uniform(-1.8, 1.8) + (cpu_target - previous.cpu_load_percent) * (0.28 if anomaly else 0.2 if self._load_reduced else 0.08), 18, 46 if anomaly else 39)
        memory = _bounded(previous.memory_usage_percent + rng.uniform(-0.15, 0.15) + (36 - previous.memory_usage_percent) * 0.04, 32, 42)
        current = _bounded(1.45 + cpu * 0.016 + rng.uniform(-0.035, 0.035), 1.65, 2.25)
        battery = _bounded(previous.battery_level_percent - current * 0.006, 0, 100)
        voltage = _bounded(26.9 + battery * 0.014 - (current - 1.9) * 0.025, 24, 29)

        # Temperatures respond slowly to CPU load and current draw.
        heat_target = 21.4 + (cpu - 28) * 0.11 + (current - 1.9) * 1.3 + (8 if anomaly else 0)
        response = 0.12 if self._scenario == ScenarioName.TEMPERATURE_ANOMALY else 0.055
        t1 = _bounded(previous.temperature_1_c + (heat_target - previous.temperature_1_c) * response + rng.uniform(-0.025, 0.025), 17, 32)
        t2 = _bounded(previous.temperature_2_c + (heat_target + 0.7 - previous.temperature_2_c) * response * .91 + rng.uniform(-0.025, 0.025), 17, 33)
        t3 = _bounded(previous.temperature_3_c + (heat_target - 0.6 - previous.temperature_3_c) * response * .82 + rng.uniform(-0.025, 0.025), 16, 31)
        if self._scenario == ScenarioName.SINGLE_SENSOR_FAULT and self._last_step >= 9:
            t1 = _bounded(previous.temperature_1_c + 2.2, 17, 38)

        signal = _bounded(previous.signal_strength_percent + rng.uniform(-0.45, 0.45) + (87 - previous.signal_strength_percent) * 0.08, 82, 95)
        latency = _bounded(previous.communication_latency_ms + (41.5 + (87 - signal) * 0.45 - previous.communication_latency_ms) * 0.15 + rng.uniform(-0.3, 0.3), 25, 65)
        loss = _bounded(previous.packet_loss_percent + (0.1 + max(0, 84 - signal) * 0.01 - previous.packet_loss_percent) * 0.1 + rng.uniform(-0.015, 0.015), 0, 0.8)

        self._sensors = SensorReadings(
            battery_level_percent=round(battery, 2), voltage_v=round(voltage, 2), current_a=round(current, 2),
            temperature_1_c=round(t1, 2), temperature_2_c=round(t2, 2), temperature_3_c=round(t3, 2),
            cpu_load_percent=round(cpu, 2), memory_usage_percent=round(memory, 2),
            signal_strength_percent=round(signal, 2), communication_latency_ms=round(latency, 2),
            packet_loss_percent=round(loss, 2),
        )

    def _build_snapshot(self, elapsed: int) -> SimulatorSnapshot:
        subsystem_status = {
            DeviceStatus.IDLE: SubsystemStatus.STANDBY,
            DeviceStatus.RUNNING: SubsystemStatus.NOMINAL,
            DeviceStatus.PAUSED: SubsystemStatus.PAUSED,
            DeviceStatus.ENDED: SubsystemStatus.STANDBY,
        }[self._status]
        mode = {
            DeviceStatus.IDLE: SystemMode.STANDBY,
            DeviceStatus.RUNNING: SystemMode.NOMINAL,
            DeviceStatus.PAUSED: SystemMode.HOLD,
            DeviceStatus.ENDED: SystemMode.STANDBY,
        }[self._status]
        return SimulatorSnapshot(
            schema_version="1.0",
            run_id=self._run_id,
            scenario=self._scenario,
            status=self._status,
            simulation_elapsed_seconds=elapsed,
            system_mode=mode,
            subsystem_statuses=SubsystemStatuses(
                power=subsystem_status, thermal=subsystem_status,
                communications=subsystem_status, computer=subsystem_status,
            ),
            sensors=self._sensors.model_copy(deep=True),
            updated_at=self._updated_at,
        )

    def _snapshot(self) -> SimulatorSnapshot:
        elapsed = self._elapsed()
        self._advance(elapsed)
        return self._build_snapshot(math.floor(elapsed))

    def snapshot(self) -> SimulatorSnapshot:
        with self._lock:
            return self._snapshot()

    def drain_samples(self) -> list[SimulatorSnapshot]:
        """Return each new whole-second state once, in sequence order."""
        with self._lock:
            samples = self._sample_events
            self._sample_events = []
            return samples

    def drain_signed_samples(self, integrity_key: bytes):
        """Sign the queued synthetic packets before the telemetry boundary."""
        from dataclasses import replace
        from app.integrity import sign_packet

        packets = []
        for sample in self.drain_samples():
            packet = sign_packet(sample, integrity_key)
            if self._scenario == ScenarioName.REPLAYED_TELEMETRY and sample.simulation_elapsed_seconds == 10 and self._previous_signed_packet:
                packet = replace(self._previous_signed_packet, test_kind="REPLAY")
            elif self._scenario == ScenarioName.SPOOFED_TELEMETRY and sample.simulation_elapsed_seconds == 10:
                packet = replace(packet, source_id="orbitra-unregistered-virtual-test", test_kind="SPOOFING")
            elif self._scenario == ScenarioName.INVALID_SIGNATURE and sample.simulation_elapsed_seconds == 10:
                changed_sensors = sample.sensors.model_copy(update={
                    "temperature_1_c": round(sample.sensors.temperature_1_c + 8, 2)})
                packet = replace(packet, snapshot=sample.model_copy(update={"sensors": changed_sensors}),
                                 test_kind="INTEGRITY")
            packets.append(packet)
            if sample.simulation_elapsed_seconds == 9:
                self._previous_signed_packet = packet
        return packets

    def start(self, scenario: ScenarioName = ScenarioName.NORMAL_MISSION) -> SimulatorSnapshot:
        with self._lock:
            if self._status not in (DeviceStatus.IDLE, DeviceStatus.ENDED):
                raise InvalidTransition("start", self._status)
            self._reset_state()
            self._scenario = scenario
            self._rng = random.Random(self._base_seed + list(ScenarioName).index(scenario) * 1009)
            self._run_id = str(uuid4())
            self._status = DeviceStatus.RUNNING
            self._running_since = self._clock()
            self._updated_at = datetime.now(timezone.utc)
            return self._snapshot()

    def pause(self) -> SimulatorSnapshot:
        with self._lock:
            if self._status != DeviceStatus.RUNNING:
                raise InvalidTransition("pause", self._status)
            self._elapsed_before = self._elapsed()
            self._advance(self._elapsed_before)
            self._running_since = None
            self._status = DeviceStatus.PAUSED
            self._updated_at = datetime.now(timezone.utc)
            return self._snapshot()

    def resume(self) -> SimulatorSnapshot:
        with self._lock:
            if self._status != DeviceStatus.PAUSED:
                raise InvalidTransition("resume", self._status)
            self._running_since = self._clock()
            self._status = DeviceStatus.RUNNING
            self._updated_at = datetime.now(timezone.utc)
            return self._snapshot()

    def reset(self) -> SimulatorSnapshot:
        with self._lock:
            self._reset_state()
            return self._snapshot()

    def end(self) -> SimulatorSnapshot:
        with self._lock:
            if self._status not in (DeviceStatus.RUNNING, DeviceStatus.PAUSED):
                raise InvalidTransition("end", self._status)
            if self._status == DeviceStatus.RUNNING:
                self._elapsed_before = self._elapsed()
                self._advance(self._elapsed_before)
            self._running_since = None
            self._status = DeviceStatus.ENDED
            self._updated_at = datetime.now(timezone.utc)
            return self._snapshot()

    def reduce_processing_load(self) -> SimulatorSnapshot:
        with self._lock:
            if self._status != DeviceStatus.RUNNING:
                raise InvalidTransition("reduce_processing_load", self._status)
            if self._load_reduced:
                raise InvalidTransition("reduce_processing_load", self._status, "Bu sessiyada virtual hesablama yükü artıq azaldılıb.")
            self._snapshot()
            self._load_reduced = True
            self._updated_at = datetime.now(timezone.utc)
            return self._snapshot()


simulator = VirtualSpacecraftSimulator()
