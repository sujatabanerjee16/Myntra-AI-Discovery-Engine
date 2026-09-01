"""Database engine, session factory, and declarative base."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from common.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


_settings = get_settings()

engine = create_engine(
    _settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_timeout=3,
    pool_size=2,
    max_overflow=0,
    connect_args={"connect_timeout": 3},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def database_available() -> bool:
    """Return True when PostgreSQL accepts connections.

    Never block the request path for long: a sleeping Neon instance or a
    missing local Postgres must fail fast so the JSON dashboard can load.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    except Exception:  # noqa: BLE001 - connectivity must never hang the UI
        return False
