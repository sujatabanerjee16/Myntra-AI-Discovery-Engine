"""Fetch YouTube comments about Myntra wishlist and shopping behavior."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

import httpx

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.seed_loader import load_seed_records
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)


def _author_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _fetch_live_records(*, query: str, limit: int, api_key: str) -> list[RawRecord]:
    search_url = "https://www.googleapis.com/youtube/v3/search"
    comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"

    with httpx.Client(timeout=20.0) as client:
        search_resp = client.get(
            search_url,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(limit, 5),
                "key": api_key,
            },
        )
        search_resp.raise_for_status()
        video_ids = [
            item["id"]["videoId"]
            for item in search_resp.json().get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        records: list[RawRecord] = []
        skipped = 0

        for video_id in video_ids:
            comments_resp = client.get(
                comments_url,
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(limit, 20),
                    "textFormat": "plainText",
                    "key": api_key,
                },
            )
            if comments_resp.status_code >= 400:
                logger.warning("YouTube comments fetch failed for %s", video_id)
                continue

            for item in comments_resp.json().get("items", []):
                snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                text = (snippet.get("textDisplay") or "").strip()
                if not text:
                    continue

                relevance = is_relevant(text)
                if not relevance.is_relevant:
                    skipped += 1
                    continue

                comment_id = item.get("id") or text[:40]
                published = snippet.get("publishedAt")
                created_at = None
                if published:
                    try:
                        created_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    except ValueError:
                        created_at = None

                records.append(
                    RawRecord(
                        source=SourceType.youtube,
                        source_ref=f"youtube:{video_id}:{comment_id}",
                        text=text,
                        author_hash=_author_hash(
                            str(snippet.get("authorDisplayName") or comment_id)
                        ),
                        language="en",
                        created_at=created_at,
                        metadata={
                            "video_id": video_id,
                            "like_count": snippet.get("likeCount"),
                        },
                        matched_signals=list(relevance.matched_signals),
                    )
                )

    logger.info("YouTube live fetch: kept %s comments, skipped %s unrelated", len(records), skipped)
    return records


def fetch_youtube_records(
    *,
    query: str | None = None,
    limit: int | None = None,
    use_live: bool | None = None,
) -> list[RawRecord]:
    """Fetch YouTube comments; uses seeds unless API key + live fetch are enabled."""
    settings = get_settings()
    query = query or settings.youtube_search_query
    limit = limit or settings.youtube_fetch_limit
    use_live = settings.youtube_live_fetch_enabled if use_live is None else use_live

    if use_live and settings.youtube_api_key:
        try:
            return _fetch_live_records(query=query, limit=limit, api_key=settings.youtube_api_key)
        except Exception:
            logger.exception("YouTube live fetch failed; falling back to seed data")

    return load_seed_records(SourceType.youtube)
