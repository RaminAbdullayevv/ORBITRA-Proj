from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def database_is_reachable() -> bool:
    with Session(engine) as session:
        return session.execute(text("SELECT 1")).scalar_one() == 1

