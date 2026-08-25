"""Load connector seed records from local JSON files."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common.models import SourceType
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seeds"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


def load_seed_records(
    source: SourceType,
    *,
    seed_path: Path | None = None,
    always_include: bool = False,
) -> list[RawRecord]:
    """Load normalized records from ``data/seeds/{source}.json``."""
    path = seed_path or (SEEDS_DIR / f"{source.value}.json")
    if not path.is_file():
        logger.info("No seed file for %s at %s", source.value, path)
        return []

    payload: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    records: list[RawRecord] = []
    skipped = 0

    for item in payload:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        relevance = is_relevant(text, always_include=always_include)
        if not relevance.is_relevant:
            skipped += 1
            continue

        source_ref = item.get("source_ref") or f"{source.value}:seed:{len(records)}"
        records.append(
            RawRecord(
                source=source,
                source_ref=source_ref,
                text=text,
                author_hash=item.get("author_hash"),
                language=item.get("language", "en"),
                created_at=_parse_datetime(item.get("created_at")),
                metadata=item.get("metadata") or {},
                matched_signals=list(relevance.matched_signals),
            )
        )

    logger.info(
        "Seed loader %s: kept %s records, skipped %s unrelated",
        source.value,
        len(records),
        skipped,
    )
    return records
