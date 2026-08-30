"""Export full raw rows from the live PostgreSQL database (read-only).

This does not use the JSON fallback or dashboard aggregates. It SELECTs every
row from the storage / analytics tables so you can see what is actually stored.

Usage (from the repo root):

  # Local / current .env (common.config.get_settings → DATABASE_URL or POSTGRES_*)
  py -3 scripts/export_live_data.py

  # Explicit production / Render URL (overrides .env for this run only)
  py -3 scripts/export_live_data.py --database-url "$DATABASE_URL"

  # Optional: also dump chunk embedding vectors (large)
  py -3 scripts/export_live_data.py --include-embeddings

Output lands in data/live_export/ (JSON + CSV per table, plus _manifest.json).
The script never writes to the database.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, defer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from common.models import (
    Chunk,
    CompetitiveAggregate,
    ConversionSnapshot,
    Document,
    Insight,
    ReasonAggregate,
    WishlistEvent,
)

DEFAULT_OUTPUT = ROOT / "data" / "live_export"

# Chunk.embedding is omitted unless --include-embeddings: 1024-dim vectors
# dwarf the rest of the row and are not useful for content verification.
EXPORT_TABLES: list[tuple[str, type, tuple[str, ...]]] = [
    ("documents", Document, ()),
    ("chunks", Chunk, ("embedding",)),
    ("insights", Insight, ()),
    ("reason_aggregates", ReasonAggregate, ()),
    ("competitive_aggregates", CompetitiveAggregate, ()),
    ("wishlist_events", WishlistEvent, ()),
    ("conversion_snapshots", ConversionSnapshot, ()),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only full-table export of the live database.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy URL. Defaults to get_settings().sqlalchemy_url (DATABASE_URL / POSTGRES_*).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
        help="Directory for JSON/CSV/manifest (default: data/live_export).",
    )
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Include chunks.embedding in the export (very large).",
    )
    return parser.parse_args()


def _normalize_sqlalchemy_url(raw: str) -> str:
    url = raw.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _safe_host_info(url: str) -> dict[str, str]:
    """Hostname + db name only — never user, password, or query string."""
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    host = parsed.hostname or "unknown"
    db_name = (parsed.path or "/").lstrip("/") or "unknown"
    if host in {"127.0.0.1", "localhost", "::1"}:
        hint = "local"
    elif "neon.tech" in host or "render.com" in host or "amazonaws.com" in host:
        hint = "prod"
    else:
        hint = "unknown"
    return {
        "database_host": host,
        "database_name": db_name,
        "environment_hint": hint,
    }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
        return None
    return value


def _row_to_dict(instance: Any, *, skip: set[str]) -> dict[str, Any]:
    mapper = inspect(instance).mapper
    row: dict[str, Any] = {}
    for column in mapper.column_attrs:
        name = column.key
        if name in skip:
            continue
        row[name] = _jsonable(getattr(instance, name))
    return row


def _flatten_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_csv_cell(row.get(key)) for key in fieldnames})


def _export_table(
    session: Session,
    table_name: str,
    model: type,
    skip_columns: set[str],
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        stmt = select(model)
        if skip_columns:
            stmt = stmt.options(*(defer(getattr(model, name)) for name in skip_columns if hasattr(model, name)))
        instances = session.scalars(stmt).all()
        return [_row_to_dict(item, skip=skip_columns) for item in instances], None
    except Exception as exc:  # table missing or permission error — keep other tables
        session.rollback()
        session.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
        return [], f"{type(exc).__name__}: {exc}"


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    raw_url = args.database_url or settings.sqlalchemy_url
    url = _normalize_sqlalchemy_url(raw_url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    host_info = _safe_host_info(url)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_timeout=15,
        connect_args={"connect_timeout": 15},
        future=True,
    )

    exported_at = datetime.now(UTC).isoformat()
    counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    skipped_columns: dict[str, list[str]] = {}

    with Session(engine) as session:
        session.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
        session.execute(text("SELECT 1"))

        for table_name, model, default_skip in EXPORT_TABLES:
            skip = set(default_skip)
            if table_name == "chunks" and args.include_embeddings:
                skip.discard("embedding")
            if skip:
                skipped_columns[table_name] = sorted(skip)

            rows, error = _export_table(session, table_name, model, skip)
            if error:
                errors[table_name] = error
                counts[table_name] = 0
                print(f"{table_name:28}  ERROR  {error}", file=sys.stderr)
                continue

            _write_json(output_dir / f"{table_name}.json", rows)
            _write_csv(output_dir / f"{table_name}.csv", rows)
            counts[table_name] = len(rows)
            print(f"{table_name:28}  {len(rows):>7} rows")

    manifest = {
        "exported_at": exported_at,
        "read_only": True,
        **host_info,
        "app_environment": settings.environment,
        "row_counts": counts,
        "skipped_columns": skipped_columns,
        "output_dir": str(output_dir.resolve()),
    }
    if errors:
        manifest["errors"] = errors
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print(f"Host: {host_info['database_host']}  ({host_info['environment_hint']})")
    print(f"Wrote {output_dir.resolve()}")
    engine.dispose()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
