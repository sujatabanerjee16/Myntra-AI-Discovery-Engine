"""Fetch Reddit discussions about Myntra wishlist behavior."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import httpx

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.seed_loader import load_seed_records
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)

_USER_AGENT = "wishlist-discovery-engine/0.1 (research bot)"


def _author_hash(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:32]


def _fetch_live_records(*, query: str, limit: int) -> list[RawRecord]:
    url = "https://www.reddit.com/search.json"
    params = {"q": query, "sort": "new", "limit": min(limit, 100), "type": "link"}

    with httpx.Client(timeout=20.0, headers={"User-Agent": _USER_AGENT}) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    records: list[RawRecord] = []
    skipped = 0

    for child in payload.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = (post.get("title") or "").strip()
        body = (post.get("selftext") or "").strip()
        text = f"{title}\n\n{body}".strip() if body else title
        if not text:
            continue

        relevance = is_relevant(text)
        if not relevance.is_relevant:
            skipped += 1
            continue

        post_id = post.get("id") or post.get("name") or text[:40]
        created = post.get("created_utc")
        created_at = datetime.fromtimestamp(float(created), tz=UTC) if created is not None else None

        records.append(
            RawRecord(
                source=SourceType.reddit,
                source_ref=f"reddit:{post.get('subreddit', 'unknown')}:{post_id}",
                text=text,
                author_hash=_author_hash(str(post.get("author") or post_id)),
                language="en",
                created_at=created_at,
                metadata={
                    "subreddit": post.get("subreddit"),
                    "permalink": post.get("permalink"),
                    "score": post.get("score"),
                },
                matched_signals=list(relevance.matched_signals),
            )
        )

    logger.info("Reddit live fetch: kept %s posts, skipped %s unrelated", len(records), skipped)
    return records


def fetch_reddit_records(
    *,
    query: str | None = None,
    limit: int | None = None,
    use_live: bool | None = None,
) -> list[RawRecord]:
    """Fetch Reddit posts; falls back to local seeds when live fetch is disabled."""
    settings = get_settings()
    query = query or settings.reddit_search_query
    limit = limit or settings.reddit_fetch_limit
    use_live = settings.reddit_live_fetch_enabled if use_live is None else use_live

    if use_live:
        try:
            return _fetch_live_records(query=query, limit=limit)
        except Exception:
            logger.exception("Reddit live fetch failed; falling back to seed data")

    return load_seed_records(SourceType.reddit)
