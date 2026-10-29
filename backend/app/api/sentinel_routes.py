"""Authenticated, bounded read API for persisted Sentinel decisions."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import Principal, current_principal
from app.telemetry import telemetry


router = APIRouter(prefix="/api/v1/sentinel", tags=["sentinel"])


@router.get("/overview")
async def overview(run_id: str | None = None, _: Principal = Depends(current_principal)) -> dict:
    return await telemetry.trust_overview(run_id)


@router.get("/runs/{run_id}/decisions")
async def decisions(run_id: str, before_id: int | None = Query(default=None, ge=1),
                    limit: int = Query(default=30, ge=1, le=100),
                    _: Principal = Depends(current_principal)) -> dict:
    result = await telemetry.trust_decisions(run_id, before_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/runs/{run_id}/decisions/{assessment_id}")
async def decision(run_id: str, assessment_id: int, _: Principal = Depends(current_principal)) -> dict:
    result = await telemetry.trust_decision(run_id, assessment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found for run")
    return result
