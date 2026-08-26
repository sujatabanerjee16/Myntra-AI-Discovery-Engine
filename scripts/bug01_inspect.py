"""Inspect Neon schema readiness for BUG-01."""

from __future__ import annotations

from sqlalchemy import text

from common.config import get_settings
from common.db import SessionLocal, database_available


def main() -> None:
    get_settings.cache_clear()
    database_available.cache_clear()
    print("available", database_available(), flush=True)
    session = SessionLocal()
    try:
        vector = session.execute(
            text("select extname from pg_extension where extname='vector'")
        ).scalar()
        print("vector", vector, flush=True)
        try:
            chunks = session.execute(text("select count(*) from chunks")).scalar()
            embedded = session.execute(
                text("select count(*) from chunks where embedding is not null")
            ).scalar()
            print("chunks", chunks, "embedded", embedded, flush=True)
        except Exception as exc:  # noqa: BLE001
            print("chunks_query", type(exc).__name__, exc, flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
