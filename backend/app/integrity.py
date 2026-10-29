"""Canonical local simulator packet format and HMAC-SHA256 verification."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from dataclasses import field
from uuid import uuid4

from app.simulator import SimulatorSnapshot


SOURCE_ID = "orbitra-local-simulator"


@dataclass(frozen=True)
class SignedTelemetryPacket:
    snapshot: SimulatorSnapshot
    source_id: str
    signature: str
    packet_id: str = field(default_factory=lambda: str(uuid4()))
    test_kind: str | None = None


def canonical_bytes(snapshot: SimulatorSnapshot, source_id: str) -> bytes:
    if snapshot.run_id is None:
        raise ValueError("Telemetry packet requires run_id")
    payload = {
        "schema_version": snapshot.schema_version,
        "run_id": snapshot.run_id,
        "scenario": snapshot.scenario.value if snapshot.scenario else None,
        "source_id": source_id,
        "sequence_number": snapshot.simulation_elapsed_seconds,
        "sample_time": snapshot.updated_at.isoformat(),
        "status": snapshot.status.value,
        "sensors": snapshot.sensors.model_dump(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sign_packet(snapshot: SimulatorSnapshot, key: bytes, source_id: str = SOURCE_ID) -> SignedTelemetryPacket:
    signature = hmac.new(key, canonical_bytes(snapshot, source_id), hashlib.sha256).hexdigest()
    return SignedTelemetryPacket(snapshot=snapshot, source_id=source_id, signature=signature)


def verify_packet(packet: SignedTelemetryPacket, key: bytes) -> bool:
    try:
        expected = hmac.new(key, canonical_bytes(packet.snapshot, packet.source_id), hashlib.sha256).hexdigest()
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, packet.signature)


CONTROL_VERSION = "1.0"


def canonical_control_bytes(action: str, snapshot: SimulatorSnapshot) -> bytes:
    payload = {"schema_version": CONTROL_VERSION, "action": action,
               "snapshot": snapshot.model_dump(mode="json")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sign_control(action: str, snapshot: SimulatorSnapshot, key: bytes) -> str:
    return hmac.new(key, canonical_control_bytes(action, snapshot), hashlib.sha256).hexdigest()


def verify_control(action: str, snapshot: SimulatorSnapshot, signature: str, key: bytes) -> bool:
    try:
        expected = sign_control(action, snapshot, key)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, signature)
