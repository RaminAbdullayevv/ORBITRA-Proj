from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from urllib.parse import urlsplit

from app.auth import (COOKIE_NAME, SESSION_HOURS, Principal, csrf_for_token,
                      current_principal, require_csrf, security)
from app.config import settings


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class IdentityResponse(BaseModel):
    user_id: int
    username: str
    role: str
    expires_at: str
    csrf_token: str


def identity(principal: Principal) -> IdentityResponse:
    return IdentityResponse(user_id=principal.user_id, username=principal.username, role=principal.role,
                            expires_at=principal.expires_at.isoformat(), csrf_token=csrf_for_token(principal.token))


@router.post("/login", response_model=IdentityResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> IdentityResponse:
    if request.headers.get("origin") != settings.frontend_origin:
        raise HTTPException(status_code=403, detail="Giriş origin yoxlaması uğursuz oldu.")
    demo_account = payload.username.strip().lower() in ("admin", "virtual")
    local_origin = urlsplit(settings.frontend_origin).hostname in ("localhost", "127.0.0.1", "::1")
    local_client = request.client is not None and request.client.host in ("127.0.0.1", "::1", "testclient")
    if settings.demo_local_only and demo_account and (not local_origin or not local_client):
        raise HTTPException(status_code=403, detail="Demo hesabı yalnız lokal bağlantı üçündür.")
    prior = security.authenticate(request.cookies.get(COOKIE_NAME))
    principal, token = security.login(payload.username, payload.password)
    if prior is not None:
        security.logout(prior)
        from app.telemetry import telemetry
        await telemetry.revoke_token(prior.token)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_HOURS * 3600, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return identity(principal)


@router.get("/me", response_model=IdentityResponse)
def me(response: Response, principal: Principal = Depends(current_principal)) -> IdentityResponse:
    response.headers["Cache-Control"] = "no-store"
    return identity(principal)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, principal: Principal = Depends(current_principal)) -> None:
    require_csrf(request, principal)
    security.logout(principal)
    from app.telemetry import telemetry
    await telemetry.revoke_token(principal.token)
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.cookie_secure, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
