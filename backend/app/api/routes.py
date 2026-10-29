from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.database import database_is_reachable


router = APIRouter(prefix="/api/v1")


class HealthResponse(BaseModel):
    status: str
    database: str


class AppInfoResponse(BaseModel):
    name: str
    phase: int
    simulation_only: bool


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        if database_is_reachable():
            return HealthResponse(status="ok", database="connected")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    raise HTTPException(status_code=503, detail="Database check failed")


@router.get("/app-info", response_model=AppInfoResponse)
def app_info() -> AppInfoResponse:
    return AppInfoResponse(name="ORBITRA", phase=8, simulation_only=True)

