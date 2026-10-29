from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.security_routes import router as security_router
from app.api.report_routes import router as report_router
from app.api.simulator_routes import router as simulator_router
from app.api.telemetry_routes import router as telemetry_router
from app.api.sentinel_routes import router as sentinel_router
from app.auth import COOKIE_NAME, security, require_monitor
from app.config import settings
from app.telemetry import telemetry


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.telemetry_hmac_key_bytes is None:
        raise RuntimeError("TELEMETRY_HMAC_KEY is required")
    if settings.frontend_origin.startswith("https://") and not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE must be true for an HTTPS origin")
    security.ensure_initial_users()
    await telemetry.start()
    try:
        yield
    finally:
        await telemetry.stop()


app = FastAPI(title="ORBITRA API", version="0.9.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(security_router, dependencies=[Depends(require_monitor)])
app.include_router(report_router, dependencies=[Depends(require_monitor)])
app.include_router(simulator_router)
app.include_router(telemetry_router)
app.include_router(sentinel_router, dependencies=[Depends(require_monitor)])



# A built frontend is served by this same backend in a one-domain deployment.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{page_path:path}", include_in_schema=False)
def frontend_page(page_path: str, request: Request):
    if page_path.startswith("api/") or page_path.startswith("assets/"):
        raise HTTPException(status_code=404)
    if page_path not in ("", "login", "virtual-device", "mission-control", "security",
                         "ai-alerts", "digital-twin", "mission-report", "telemetry-trust"):
        raise HTTPException(status_code=404)
    principal = security.authenticate(request.cookies.get(COOKIE_NAME))
    if page_path == "":
        return RedirectResponse("/virtual-device" if principal and principal.role == "VIRTUAL"
                                else "/mission-control" if principal else "/login")
    if page_path != "login":
        if principal is None:
            return RedirectResponse("/login")
        if (page_path == "virtual-device") != (principal.role == "VIRTUAL"):
            raise HTTPException(status_code=403, detail="Bu səhifəyə giriş icazəsi yoxdur.")
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend qurulmayıb: npm run build")
    return FileResponse(index, headers={"Cache-Control": "no-store"})
