"""Connector registry for all Phase 7 source types."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from ingestion.connectors.play_store import fetch_play_store_records
from ingestion.connectors.product_review import fetch_product_review_records
from ingestion.connectors.reddit import fetch_reddit_records
from ingestion.connectors.research_excel import fetch_all_research_records
from ingestion.connectors.social import fetch_social_records
from ingestion.connectors.youtube import fetch_youtube_records
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)

ALL_SOURCES: tuple[str, ...] = (
    "research",
    "play_store",
    "reddit",
    "youtube",
    "product_review",
    "social",
)

ConnectorFn = Callable[..., list[RawRecord]]


def _resolve_research_paths(
    research_excel_path: str | None = None,
    research_excel_paths: list[str] | None = None,
) -> list[str]:
    paths: list[str] = []
    for raw in [*(research_excel_paths or []), research_excel_path]:
        if not raw:
            continue
        path = str(raw).strip()
        if path and path not in paths:
            paths.append(path)
    return paths


def _fetch_research_bundle(
    research_excel_path: str | None = None,
    research_excel_paths: list[str] | None = None,
    **_kwargs,
) -> list[RawRecord]:
    paths = _resolve_research_paths(research_excel_path, research_excel_paths)
    existing = [p for p in paths if Path(p).exists()]
    missing = [p for p in paths if not Path(p).exists()]
    for path in missing:
        logger.warning("Research Excel not found, skipping: %s", path)
    if not existing:
        logger.warning("No research Excel workbooks found among: %s", paths)
        return []
    return fetch_all_research_records(existing)


CONNECTOR_REGISTRY: dict[str, ConnectorFn] = {
    "research": _fetch_research_bundle,
    "play_store": lambda **kwargs: fetch_play_store_records(limit=kwargs.get("play_store_limit")),
    "reddit": lambda **_kwargs: fetch_reddit_records(),
    "youtube": lambda **_kwargs: fetch_youtube_records(),
    "product_review": lambda **_kwargs: fetch_product_review_records(),
    "social": lambda **_kwargs: fetch_social_records(),
}


def fetch_source_records(source: str, **kwargs) -> list[RawRecord]:
    """Fetch raw records for a supported source key."""
    key = source.strip().lower()
    connector = CONNECTOR_REGISTRY.get(key)
    if connector is None:
        raise ValueError(f"Unsupported source: {source}. Choose from {list(ALL_SOURCES)}")
    records = connector(**kwargs)
    logger.info("Connector %s returned %s records", key, len(records))
    return records
