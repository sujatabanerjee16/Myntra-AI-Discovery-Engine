"""Fetch Reddit discussions about Myntra wishlist behavior."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

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


_APIFY_ACTORS = (
    "trudax~reddit-scraper-lite",
    "trudax~reddit-scraper",
)


def _apify_item_to_record(item: dict) -> RawRecord | None:
    title = str(item.get("title") or item.get("parsedTitle") or "").strip()
    body = str(
        item.get("body")
        or item.get("selftext")
        or item.get("text")
        or item.get("description")
        or ""
    ).strip()
    # Skip comment-only / community-only rows with no post text.
    if item.get("dataType") in {"comment", "community", "user"} and not title:
        return None
    text = f"{title}\n\n{body}".strip() if body else title
    if not text:
        return None
    relevance = is_relevant(text)
    if not relevance.is_relevant or "wishlist_usage" not in relevance.matched_signals:
        return None
    subreddit = (
        item.get("communityName")
        or item.get("parsedCommunityName")
        or item.get("subreddit")
        or "unknown"
    )
    subreddit = str(subreddit).removeprefix("r/")
    post_id = str(item.get("id") or item.get("parsedId") or item.get("postId") or text[:40])
    created = item.get("createdAt") or item.get("created_utc") or item.get("timestamp")
    created_at = None
    if created is not None:
        try:
            created_at = datetime.fromtimestamp(float(created), tz=UTC)
        except (TypeError, ValueError):
            try:
                created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            except ValueError:
                created_at = None
    permalink = item.get("url") or item.get("permalink") or item.get("link")
    return RawRecord(
        source=SourceType.reddit,
        source_ref=f"reddit:{subreddit}:{post_id}",
        text=text,
        author_hash=_author_hash(str(item.get("username") or item.get("author") or post_id)),
        language="en",
        created_at=created_at,
        metadata={
            "subreddit": subreddit,
            "permalink": permalink,
            "score": item.get("upVotes") or item.get("score"),
            "via": "apify",
        },
        matched_signals=list(relevance.matched_signals),
    )


def _resolve_apify_token(settings) -> str | None:
    if settings.apify_api_token:
        return settings.apify_api_token
    try:
        from dotenv import dotenv_values
    except ImportError:
        return None
    vals = dotenv_values(Path(".env"))
    for key in ("APIFY_API_TOKEN", "Apify_API_TOKEN", "apify_api_token"):
        value = vals.get(key)
        if value:
            return value
    return None


def _apify_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _apify_error_snippet(response: httpx.Response) -> str:
    return (response.text or "")[:240]


def _fetch_apify_records(*, query: str, limit: int, token: str, actor: str) -> list[RawRecord]:
    actor_id = actor.replace("/", "~")
    payload = {
        "searches": [query],
        "searchPosts": True,
        "searchComments": False,
        "searchCommunities": False,
        "searchUsers": False,
        "skipComments": True,
        "maxItems": min(limit, 25),
        "maxPostCount": min(limit, 25),
        "maxComments": 0,
        "sort": "relevance",
        "time": "all",
        "proxy": {"useApifyProxy": True},
    }
    headers = _apify_headers(token)
    with httpx.Client(timeout=30.0) as client:
        items = _reuse_latest_apify_items(client, actor_id, headers)
        if items is None:
            items = _run_apify_actor(client, actor_id, headers, payload)
    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected Apify payload type: {type(items)}")
    records: list[RawRecord] = []
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        record = _apify_item_to_record(item)
        if record is None:
            skipped += 1
            continue
        records.append(record)
    logger.info("Apify Reddit fetch via %s: kept %s, skipped %s", actor_id, len(records), skipped)
    return records


def _reuse_latest_apify_items(client: httpx.Client, actor_id: str, headers: dict[str, str]) -> list | None:
    listing = client.get(
        f"https://api.apify.com/v2/acts/{actor_id}/runs",
        headers=headers,
        params={"limit": 5, "desc": "true"},
    )
    if listing.status_code >= 400:
        return None
    for run in (listing.json().get("data") or {}).get("items") or []:
        if run.get("status") != "SUCCEEDED":
            continue
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            continue
        items_resp = client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            headers=headers,
            params={"format": "json"},
        )
        if items_resp.status_code >= 400:
            continue
        items = items_resp.json()
        if isinstance(items, list) and items:
            logger.info("Reusing Apify run %s (%s items)", run.get("id"), len(items))
            return items
    return None


def _run_apify_actor(client: httpx.Client, actor_id: str, headers: dict[str, str], payload: dict) -> list:
    start = client.post(
        f"https://api.apify.com/v2/acts/{actor_id}/runs",
        json=payload,
        headers=headers,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"Apify start HTTP {start.status_code}: {_apify_error_snippet(start)}")
    run = start.json().get("data") or {}
    run_id = run.get("id")
    dataset_id = run.get("defaultDatasetId")
    if not run_id:
        raise RuntimeError("Apify start response missing run id")
    status = run.get("status")
    deadline = time.time() + 300
    while status in {None, "READY", "RUNNING", "TIMING-OUT"} and time.time() < deadline:
        logger.info("Apify Reddit run %s status=%s", run_id, status or "READY")
        time.sleep(8)
        poll = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}", headers=headers)
        if poll.status_code >= 400:
            raise RuntimeError(f"Apify poll HTTP {poll.status_code}: {_apify_error_snippet(poll)}")
        body = poll.json().get("data") or {}
        status = body.get("status")
        dataset_id = body.get("defaultDatasetId") or dataset_id
    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run {run_id} ended with status={status}")
    if not dataset_id:
        raise RuntimeError(f"Apify run {run_id} has no dataset")
    response = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        headers=headers,
        params={"format": "json"},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Apify items HTTP {response.status_code}: {_apify_error_snippet(response)}")
    return response.json()


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
        token = _resolve_apify_token(settings)
        if token:
            actors = [settings.apify_reddit_actor.replace("/", "~"), *_APIFY_ACTORS]
            seen: set[str] = set()
            for actor in actors:
                if actor in seen:
                    continue
                seen.add(actor)
                try:
                    return _fetch_apify_records(
                        query=query, limit=limit, token=token, actor=actor
                    )
                except Exception as exc:
                    logger.warning("Apify actor %s failed: %s", actor, type(exc).__name__)
            logger.warning("All Apify Reddit actors failed; trying public Reddit search")
        try:
            return _fetch_live_records(query=query, limit=limit)
        except Exception:
            logger.exception("Reddit live fetch failed; falling back to seed data")

    return load_seed_records(SourceType.reddit)
