from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from app.auth import Principal, require_monitor, require_websocket
from app.ai_analysis import AIEventPayload
from app.telemetry import OperatorEventHistory, TelemetryHistory, TelemetryState, telemetry


router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/state", response_model=TelemetryState)
async def get_telemetry_state(run_id: str | None = None, _: Principal = Depends(require_monitor)) -> TelemetryState:
    try:
        state = await telemetry.state(run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc
    if run_id is not None and state.run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return state


@router.get("/runs/{run_id}/samples", response_model=TelemetryHistory)
async def get_run_samples(
    run_id: str,
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int = Query(default=300, ge=1, le=600),
    _: Principal = Depends(require_monitor),
) -> TelemetryHistory:
    try:
        history = await telemetry.history(run_id, after_sequence, limit)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc
    if history is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return history


@router.get("/runs/{run_id}/events", response_model=OperatorEventHistory)
async def get_run_events(
    run_id: str,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=600),
    _: Principal = Depends(require_monitor),
) -> OperatorEventHistory:
    try:
        history = await telemetry.event_history(run_id, after_id, limit)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc
    if history is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return history


@router.get("/runs/{run_id}/ai-events", response_model=list[AIEventPayload])
async def get_run_ai_events(run_id: str, _: Principal = Depends(require_monitor)) -> list[AIEventPayload]:
    try:
        events = await telemetry.ai_event_history(run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Telemetry database unavailable") from exc
    if events is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return events


@router.websocket("/ws")
async def telemetry_socket(websocket: WebSocket) -> None:
    principal = await require_websocket(websocket)
    if principal is None:
        return
    try:
        await telemetry.connect(websocket, principal)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        telemetry.disconnect(websocket)
