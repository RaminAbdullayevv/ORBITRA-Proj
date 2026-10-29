"""Local, authenticated Device -> Main ingestion boundary."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.integrity import SignedTelemetryPacket
from app.simulator import SimulatorSnapshot
from app.telemetry import telemetry

router = APIRouter(prefix="/api/v1/device-ingress", tags=["device-ingress"])
LOCAL_HOSTS = {"127.0.0.1", "::1", "testclient"}


class ControlEnvelope(BaseModel):
    action: str
    snapshot: SimulatorSnapshot
    signature: str


class PacketEnvelope(BaseModel):
    snapshot: SimulatorSnapshot
    source_id: str
    signature: str
    packet_id: str


def require_local(request: Request) -> None:
    if request.client is None or request.client.host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Device ingress is localhost-only.")


@router.post("/control")
async def control(request: Request, envelope: ControlEnvelope) -> dict:
    require_local(request)
    try:
        return await telemetry.receive_control(envelope.action, envelope.snapshot, envelope.signature)
    except ValueError as exc:
        status = 403 if str(exc) == "INVALID_CONTROL_SIGNATURE" else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/packet")
async def packet(request: Request) -> dict:
    require_local(request)
    try:
        raw = await request.json()
    except ValueError:
        raw = {}
    try:
        envelope = PacketEnvelope.model_validate(raw)
    except ValidationError:
        return await telemetry.reject_malformed(raw)
    signed = SignedTelemetryPacket(
        snapshot=envelope.snapshot, source_id=envelope.source_id,
        signature=envelope.signature, packet_id=envelope.packet_id,
    )
    try:
        return await telemetry.receive_packet(signed)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
