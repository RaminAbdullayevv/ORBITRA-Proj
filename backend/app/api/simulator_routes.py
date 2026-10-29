import asyncio
from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.simulator import InvalidTransition, ScenarioName, SimulatorSnapshot
from app.telemetry import telemetry
from app.models import RejectedTelemetry, TelemetrySample, OperatorEvent
from app.auth import Principal, require_virtual, require_websocket, security, COOKIE_NAME


router = APIRouter(prefix="/api/v1/virtual-device", tags=["virtual-device"])


class StartMissionRequest(BaseModel):
    scenario: ScenarioName = ScenarioName.NORMAL_MISSION


async def _perform(action: str, principal: Principal, scenario: ScenarioName = ScenarioName.NORMAL_MISSION) -> SimulatorSnapshot:
    try:
        return await telemetry.command(action, scenario, actor=principal)
    except InvalidTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_transition",
                "action": exc.action,
                "status": exc.status.value,
                "message": exc.reason,
            },
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc


@router.get("", response_model=SimulatorSnapshot)
async def get_virtual_device(_: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    try:
        return await telemetry.current()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc


@router.post("/start", response_model=SimulatorSnapshot)
async def start_virtual_device(payload: StartMissionRequest | None = Body(default=None),
                               principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("start", principal, payload.scenario if payload else ScenarioName.NORMAL_MISSION)


@router.post("/pause", response_model=SimulatorSnapshot)
async def pause_virtual_device(principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("pause", principal)


@router.post("/resume", response_model=SimulatorSnapshot)
async def resume_virtual_device(principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("resume", principal)


@router.post("/reset", response_model=SimulatorSnapshot)
async def reset_virtual_device(principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("reset", principal)


@router.post("/end", response_model=SimulatorSnapshot)
async def end_virtual_device(principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("end", principal)


@router.post("/reduce-processing-load", response_model=SimulatorSnapshot)
async def reduce_virtual_processing_load(principal: Principal = Depends(require_virtual)) -> SimulatorSnapshot:
    return await _perform("reduce_processing_load", principal)


def recent_deliveries(run_id: str | None) -> list[dict]:
    if not run_id:
        return []
    with Session(security.engine) as db:
        samples = list(db.scalars(select(TelemetrySample).where(TelemetrySample.run_id == run_id)
            .order_by(TelemetrySample.id.desc()).limit(20)))
        rejected = list(db.scalars(select(RejectedTelemetry).where(RejectedTelemetry.run_id == run_id)
            .order_by(RejectedTelemetry.rejected_at.desc()).limit(20)))
        commands = list(db.scalars(select(OperatorEvent).where(OperatorEvent.run_id == run_id)
            .order_by(OperatorEvent.event_number.desc()).limit(20)))
    rows = [dict(id=f"sample-{row.id}", kind="packet", run_id=run_id,
                 sequence_number=row.sequence_number, packet_id=None, sent_at=row.sample_time,
                 result="ACCEPTED", reason_code=None, detail=None) for row in samples]
    rows += [dict(id=f"rejected-{row.rejection_id}", kind="packet", run_id=run_id,
                  sequence_number=row.sequence_number, packet_id=row.packet_id, sent_at=row.rejected_at,
                  result="REJECTED", reason_code=row.reason_code, detail=row.reason) for row in rejected]
    rows += [dict(id=f"control-{row.event_number}", kind="control", run_id=run_id,
                  sequence_number=None, packet_id=None, sent_at=row.received_at,
                  result="ACCEPTED" if row.outcome == "SUCCESS" else "REJECTED",
                  reason_code=None if row.outcome == "SUCCESS" else "INVALID_TRANSITION",
                  detail=row.reason) for row in commands]
    return sorted(rows, key=lambda row: row["sent_at"], reverse=True)[:40]


async def device_state() -> dict:
    snapshot = await telemetry.current()
    return {"device": snapshot.model_dump(mode="json"), "deliveries": recent_deliveries(snapshot.run_id)}


@router.get("/state")
async def get_device_state(_: Principal = Depends(require_virtual)) -> dict:
    return await device_state()


@router.websocket("/ws")
async def device_socket(websocket: WebSocket) -> None:
    principal = await require_websocket(websocket, virtual=True)
    if principal is None:
        return
    await websocket.accept()
    try:
        while True:
            if security.authenticate(websocket.cookies.get(COOKIE_NAME)) is None:
                await websocket.close(code=1008)
                return
            await websocket.send_json({"type": "device_state", **(await device_state())})
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError):
        return
