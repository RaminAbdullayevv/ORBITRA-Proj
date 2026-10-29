import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./orbitra.db")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    telemetry_hmac_key: str = os.getenv("TELEMETRY_HMAC_KEY", "")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", str(os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").startswith("https://"))).lower() == "true"
    demo_local_only: bool = os.getenv("DEMO_LOCAL_ONLY", "true").lower() == "true"

    @property
    def telemetry_hmac_key_bytes(self) -> bytes | None:
        if not self.telemetry_hmac_key:
            return None
        try:
            key = bytes.fromhex(self.telemetry_hmac_key)
        except ValueError as exc:
            raise ValueError("TELEMETRY_HMAC_KEY must be 64 hexadecimal characters") from exc
        if len(key) != 32:
            raise ValueError("TELEMETRY_HMAC_KEY must be 64 hexadecimal characters")
        return key


settings = Settings()

