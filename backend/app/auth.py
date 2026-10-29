"""Local demo identities, bounded server sessions, CSRF and role decisions."""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, WebSocket
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models import AuditEvent, User, UserSession


COOKIE_NAME = "orbitra_session"
SESSION_HOURS = 8
LOGIN_LIMIT = 5
LOGIN_WINDOW_MINUTES = 10
ROLES = ("ADMIN", "VIRTUAL", "OPERATOR", "SECURITY_ANALYST", "OBSERVER")
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_dummy_hash = password_hasher.hash("unknown-local-account")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_for_token(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"orbitra-session-csrf-v1", hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Principal:
    user_id: int
    username: str
    role: str
    session_id: str
    token: str
    expires_at: datetime


class SecurityService:
    def __init__(self, database_engine: Engine):
        self.engine = database_engine

    def create_if_missing(self, username: str, password: str, role: str) -> None:
        """Hash an initial credential once; never reset an existing password at startup."""
        if role not in ROLES or not password:
            raise ValueError("A valid role and initial password are required")
        with Session(self.engine) as db:
            if db.scalar(select(User.id).where(User.username == username)) is not None:
                return
            db.add(User(username=username, password_hash=password_hasher.hash(password), role=role,
                        created_at=utc_now().isoformat(), active=True))
            db.commit()

    def ensure_initial_users(self) -> None:
        for username, role, variable in (
            ("admin", "ADMIN", "ORBITRA_ADMIN_INITIAL_PASSWORD"),
            ("virtual", "VIRTUAL", "ORBITRA_VIRTUAL_INITIAL_PASSWORD"),
        ):
            password = os.getenv(variable)
            if password:
                self.create_if_missing(username, password, role)

    def audit(self, action: str, outcome: str, reason_code: str, *, user_id: int | None = None,
              username: str | None = None, run_id: str | None = None, incident_id: str | None = None,
              sequence_number: int | None = None, db: Session | None = None) -> None:
        row = AuditEvent(
            occurred_at=utc_now().isoformat(), user_id=user_id, username=username,
            action=action, outcome=outcome, reason_code=reason_code,
            run_id=run_id, incident_id=incident_id, sequence_number=sequence_number,
        )
        if db is not None:
            db.add(row)
        else:
            with Session(self.engine) as own_db:
                own_db.add(row)
                own_db.commit()

    def upsert_demo_user(self, username: str, password: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError("Unknown demo role")
        if len(password) < 12:
            raise ValueError("Demo password must contain at least 12 characters")
        password_hash = password_hasher.hash(password)
        with Session(self.engine) as db:
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                db.add(User(username=username, password_hash=password_hash, role=role,
                            created_at=utc_now().isoformat(), active=True))
            else:
                user.password_hash = password_hash
                user.role = role
                user.active = True
                for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))):
                    session.revoked_at = utc_now().isoformat()
            db.commit()

    def login(self, username: str, password: str) -> tuple[Principal, str]:
        normalized = username.strip().lower()
        now = utc_now()
        cutoff = (now - timedelta(minutes=LOGIN_WINDOW_MINUTES)).isoformat()
        with Session(self.engine) as db:
            failures = db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == "LOGIN", AuditEvent.outcome == "FAILED",
                AuditEvent.username == normalized, AuditEvent.occurred_at >= cutoff,
            )) or 0
            if failures >= LOGIN_LIMIT:
                self.audit("LOGIN", "DENIED", "RATE_LIMITED", username=normalized, db=db)
                db.commit()
                raise HTTPException(status_code=429, detail="Çox sayda uğursuz giriş cəhdi. Bir qədər sonra yenidən yoxlayın.")
            user = db.scalar(select(User).where(User.username == normalized, User.active.is_(True)))
            try:
                password_hasher.verify(user.password_hash if user else _dummy_hash, password)
                valid = user is not None
            except (VerificationError, VerifyMismatchError):
                valid = False
            if not valid:
                self.audit("LOGIN", "FAILED", "INVALID_CREDENTIALS", username=normalized, db=db)
                db.commit()
                raise HTTPException(status_code=401, detail="İstifadəçi adı və ya parol yanlışdır.")
            assert user is not None
            token = secrets.token_urlsafe(32)
            expires = now + timedelta(hours=SESSION_HOURS)
            session = UserSession(id=str(uuid4()), user_id=user.id, token_hash=token_digest(token),
                                  created_at=now.isoformat(), expires_at=expires.isoformat(), revoked_at=None)
            db.add(session)
            self.audit("LOGIN", "SUCCESS", "AUTHENTICATED", user_id=user.id, username=user.username, db=db)
            db.commit()
            return Principal(user.id, user.username, user.role, session.id, token, expires), token

    def authenticate(self, token: str | None) -> Principal | None:
        if not token:
            return None
        with Session(self.engine) as db:
            session = db.scalar(select(UserSession).where(UserSession.token_hash == token_digest(token)))
            if session is None or session.revoked_at is not None or datetime.fromisoformat(session.expires_at) <= utc_now():
                return None
            user = db.get(User, session.user_id)
            if user is None or not user.active:
                return None
            return Principal(user.id, user.username, user.role, session.id, token,
                             datetime.fromisoformat(session.expires_at))

    def logout(self, principal: Principal) -> None:
        with Session(self.engine) as db:
            session = db.get(UserSession, principal.session_id)
            if session is not None and session.revoked_at is None:
                session.revoked_at = utc_now().isoformat()
                self.audit("LOGOUT", "SUCCESS", "SESSION_REVOKED", user_id=principal.user_id,
                           username=principal.username, db=db)
                db.commit()


security = SecurityService(engine)


def current_principal(request: Request) -> Principal:
    principal = security.authenticate(request.cookies.get(COOKIE_NAME))
    if principal is None:
        raise HTTPException(status_code=401, detail="Giriş tələb olunur.")
    return principal


def require_csrf(request: Request, principal: Principal) -> None:
    origin = request.headers.get("origin")
    token = request.headers.get("x-csrf-token", "")
    if origin != settings.frontend_origin or not hmac.compare_digest(token, csrf_for_token(principal.token)):
        security.audit("CSRF_CHECK", "DENIED", "CSRF_REJECTED", user_id=principal.user_id,
                       username=principal.username)
        raise HTTPException(status_code=403, detail="Sorğunun CSRF yoxlaması uğursuz oldu.")


def _require_role(request: Request, principal: Principal, role: str) -> Principal:
    if principal.role not in (role, "ADMIN"):
        security.audit(request.url.path.rsplit("/", 1)[-1].upper(), "DENIED", "ROLE_DENIED",
                       user_id=principal.user_id, username=principal.username)
        raise HTTPException(status_code=403, detail="Bu əməliyyat üçün rol icazəsi yoxdur.")
    require_csrf(request, principal)
    return principal


def require_operator(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    return _require_role(request, principal, "OPERATOR")


def require_analyst(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    return _require_role(request, principal, "SECURITY_ANALYST")


def require_monitor(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role not in ("ADMIN", "OPERATOR", "SECURITY_ANALYST", "OBSERVER"):
        security.audit("MONITOR_ACCESS", "DENIED", "ROLE_DENIED", user_id=principal.user_id,
                       username=principal.username)
        raise HTTPException(status_code=403, detail="Monitorinq ekranına giriş icazəsi yoxdur.")
    return principal


def require_virtual(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != "VIRTUAL":
        security.audit("DEVICE_ACCESS", "DENIED", "ROLE_DENIED", user_id=principal.user_id,
                       username=principal.username)
        raise HTTPException(status_code=403, detail="Virtual cihaz hesabı tələb olunur.")
    if request.method != "GET":
        require_csrf(request, principal)
    return principal


async def require_websocket(websocket: WebSocket, *, virtual: bool = False) -> Principal | None:
    if websocket.headers.get("origin") != settings.frontend_origin:
        await websocket.close(code=1008)
        return None
    principal = security.authenticate(websocket.cookies.get(COOKIE_NAME))
    allowed = ("VIRTUAL",) if virtual else ("ADMIN", "OPERATOR", "SECURITY_ANALYST", "OBSERVER")
    if principal is None or principal.role not in allowed:
        await websocket.close(code=1008)
        return None
    return principal
