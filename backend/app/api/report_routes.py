"""Authenticated run list and reproducible report view."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import Principal, current_principal, require_csrf, security
from app.reports import generate_report, list_runs, read_report


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/runs")
def runs(_: Principal = Depends(current_principal)) -> list[dict]:
    return list_runs(security.engine)


@router.get("/runs/{run_id}")
def report(run_id: str, _: Principal = Depends(current_principal)) -> dict:
    result = read_report(security.engine, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sessiya tapılmadı.")
    return result


@router.post("/runs/{run_id}/generate")
def generate(run_id: str, request: Request, principal: Principal = Depends(current_principal)) -> dict:
    require_csrf(request, principal)
    try:
        generated_at = generate_report(security.engine, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if generated_at is None:
        raise HTTPException(status_code=404, detail="Sessiya tapılmadı.")
    security.audit("REPORT_GENERATE", "SUCCESS", "REPORT_READY", user_id=principal.user_id,
                   username=principal.username, run_id=run_id)
    return {"run_id": run_id, "generated_at": generated_at}
