"""Load Myntra internal wishlist/funnel behavioral events."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from internal.schemas import InternalEventRecord

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seeds"


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def load_internal_events(path: str | Path) -> list[InternalEventRecord]:
    """Load internal behavioral events from a JSON export."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Internal events file not found: {file_path}")

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    records: list[InternalEventRecord] = []

    for item in payload:
        records.append(
            InternalEventRecord(
                user_hash=item["user_hash"],
                product_id=item["product_id"],
                event_type=item["event_type"],
                category=item.get("category"),
                segment=item.get("segment"),
                price_band=item.get("price_band"),
                event_at=_parse_datetime(item["event_at"]),
                metadata=item.get("metadata") or {},
            )
        )

    logger.info("Loaded %s internal events from %s", len(records), file_path)
    return records
