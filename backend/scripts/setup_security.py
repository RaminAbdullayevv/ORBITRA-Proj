"""Local setup: create the HMAC key and idempotent administrator account.

Run from backend after Alembic migration: python -m scripts.setup_security
Only a random telemetry key is written to .env. The admin password is hashed in SQLite.
"""

import secrets
from pathlib import Path

from app.auth import security
from app.config import BACKEND_DIR


def ensure_local_key() -> None:
    path = Path(BACKEND_DIR) / ".env"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    values = dict(line.split("=", 1) for line in current.splitlines() if "=" in line and not line.lstrip().startswith("#"))
    if values.get("TELEMETRY_HMAC_KEY"):
        if len(bytes.fromhex(values["TELEMETRY_HMAC_KEY"])) != 32:
            raise ValueError("Existing TELEMETRY_HMAC_KEY must be 64 hexadecimal characters")
        return
    if "TELEMETRY_HMAC_KEY" in values:
        lines = [line for line in current.splitlines() if not line.startswith("TELEMETRY_HMAC_KEY=")]
        current = "\n".join(lines).rstrip() + "\n"
    path.write_text(current + f"TELEMETRY_HMAC_KEY={secrets.token_hex(32)}\n", encoding="utf-8")
    print("Local telemetry key created in backend/.env. Restart the backend.")


def main() -> None:
    ensure_local_key()
    security.ensure_initial_users()
    print("Configured accounts are ready. Existing credentials were not changed.")


if __name__ == "__main__":
    main()
