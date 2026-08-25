"""Fetch and filter Google Play Store reviews for the Myntra app."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.seed_loader import load_seed_records
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)


def _author_hash(review_id: str) -> str:
    return hashlib.sha256(review_id.encode()).hexdigest()[:32]


def fetch_play_store_records(
    *,
    app_id: str | None = None,
    limit: int | None = None,
    lang: str = "en",
    country: str = "in",
) -> list[RawRecord]:
    """Scrape Play Store reviews and keep only priority-signal-related feedback.

    Falls back to ``data/seeds/play_store.json`` when live scrape is unavailable.
    """
    settings = get_settings()
    app_id = app_id or settings.myntra_play_store_app_id
    limit = limit or settings.play_store_review_limit

    logger.info("Fetching up to %s Play Store reviews for %s", limit, app_id)

    try:
        from google_play_scraper import Sort, reviews

        result, _ = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=limit,
        )
    except Exception:
        logger.exception("Play Store scrape failed for %s — using seed fallback", app_id)
        return load_seed_records(SourceType.play_store)

    records: list[RawRecord] = []
    skipped = 0

    for review in result:
        content = (review.get("content") or "").strip()
        if not content:
            continue

        relevance = is_relevant(content)
        if not relevance.is_relevant:
            skipped += 1
            continue

        review_id = str(
            review.get("reviewId") or review.get("reviewCreatedVersion") or content[:40]
        )
        source_ref = f"play_store:{app_id}:{review_id}"

        at = review.get("at")
        created_at = (
            at.replace(tzinfo=UTC) if isinstance(at, datetime) and at.tzinfo is None else at
        )

        records.append(
            RawRecord(
                source=SourceType.play_store,
                source_ref=source_ref,
                text=content,
                author_hash=_author_hash(review_id),
                language=lang,
                created_at=created_at,
                metadata={
                    "score": review.get("score"),
                    "thumbs_up": review.get("thumbsUpCount"),
                    "app_id": app_id,
                    "platform": "android_play_store",
                },
                matched_signals=list(relevance.matched_signals),
            )
        )

    if not records:
        logger.info("Play Store scrape returned no relevant reviews — using seed fallback")
        return load_seed_records(SourceType.play_store)

    logger.info(
        "Play Store: kept %s relevant reviews, skipped %s unrelated",
        len(records),
        skipped,
    )
    return records
