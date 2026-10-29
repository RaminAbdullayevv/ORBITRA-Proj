"""Idempotently archive former Device SQLite history into the single Main database."""
import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import engine
from app.models import DeviceAuditHistory, DeviceDispatchHistory, DeviceRunHistory

DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "device_backend" / "orbitra_device.db"


def merge(source: Path = DEFAULT_SOURCE) -> dict[str, int]:
    if not source.is_file():
        return {"runs": 0, "dispatches": 0, "audits": 0}
    con = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        with Session(engine) as db:
            counts = {"runs": 0, "dispatches": 0, "audits": 0}
            specs = (
                ("device_runs", DeviceRunHistory, "run_id", "runs"),
                ("dispatch_attempts", DeviceDispatchHistory, "legacy_id", "dispatches"),
                ("audit_events", DeviceAuditHistory, "legacy_id", "audits"),
            )
            for table, model, key, label in specs:
                rows = con.execute(f"SELECT * FROM {table}").fetchall()
                for row in rows:
                    values = dict(row)
                    if table != "device_runs":
                        values["legacy_id"] = values.pop("id")
                    if table == "audit_events":
                        values = {name: values.get(name) for name in
                                  ("legacy_id", "occurred_at", "username", "action", "outcome",
                                   "reason_code", "run_id", "sequence_number")}
                    if db.get(model, values[key]) is None:
                        db.add(model(**values))
                        counts[label] += 1
            db.commit()
            return counts
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    print(merge(args.source))


if __name__ == "__main__":
    main()
