"""Grow the corpus toward 1000+ relevant docs from Play Store + Apify Reddit.

Keeps every priority-signal review/post (wishlist, fit, price, delay, comparison),
not only rows that literally say wishlist.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.reddit import (
    _apify_headers,
    _author_hash as reddit_author_hash,
    _resolve_apify_token,
    _run_apify_actor,
)
from ingestion.filters.relevance import is_relevant
from ingestion.pipeline import _default_run_version
from ingestion.schemas import RawRecord
from scripts.scale_wishlist_pull import _records_to_docs, merge_wishlist_docs, pull_play_store

logger = logging.getLogger(__name__)

PLAY_APPS = (
    ("com.myntra.android", 4000),
    ("com.ril.ajio", 2500),
    ("com.fsn.nykaa", 2500),
)

APIFY_SEARCHES = [
    "myntra wishlist",
    "ajio wishlist",
    "nykaa wishlist",
    "myntra size return",
    "myntra sale wait",
    "myntra review fake",
]


def pull_play_keep_relevant(app_id: str, target: int) -> tuple[int, list[RawRecord]]:
    scanned, relevant, _wish = pull_play_store(app_id, target=target)
    return scanned, relevant


def _apify_any_relevant(item: dict) -> RawRecord | None:
    title = str(item.get("title") or item.get("parsedTitle") or "").strip()
    body = str(
        item.get("body")
        or item.get("selftext")
        or item.get("text")
        or item.get("description")
        or item.get("bodyText")
        or ""
    ).strip()
    text = f"{title}\n\n{body}".strip() if body else title
    if not text:
        return None
    relevance = is_relevant(text)
    if not relevance.is_relevant:
        return None
    subreddit = str(
        item.get("communityName")
        or item.get("parsedCommunityName")
        or item.get("subreddit")
        or "unknown"
    ).removeprefix("r/")
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
    return RawRecord(
        source=SourceType.reddit,
        source_ref=f"reddit:{subreddit}:{post_id}",
        text=text,
        author_hash=reddit_author_hash(str(item.get("username") or item.get("author") or post_id)),
        language="en",
        created_at=created_at,
        metadata={
            "subreddit": subreddit,
            "permalink": item.get("url") or item.get("permalink") or item.get("link"),
            "score": item.get("upVotes") or item.get("score"),
            "via": "apify_volume",
            "dataType": item.get("dataType"),
        },
        matched_signals=list(relevance.matched_signals),
    )


def pull_apify_volume(token: str, actor: str) -> tuple[int, list[RawRecord]]:
    actor_id = actor.replace("/", "~")
    payload = {
        "searches": APIFY_SEARCHES,
        "searchPosts": True,
        "searchComments": True,
        "searchCommunities": False,
        "searchUsers": False,
        "skipComments": False,
        "maxItems": 250,
        "maxPostCount": 180,
        "maxComments": 80,
        "sort": "relevance",
        "time": "year",
        "proxy": {"useApifyProxy": True},
    }
    headers = _apify_headers(token)
    with httpx.Client(timeout=60.0) as client:
        items = _run_apify_actor(client, actor_id, headers, payload)
    if not isinstance(items, list):
        return 0, []
    records: list[RawRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = _apify_any_relevant(item)
        if record is not None:
            records.append(record)
    return len(items), records


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    run_version = _default_run_version()
    kept: list[RawRecord] = []

    play_scanned = 0
    play_kept = 0
    for app_id, target in PLAY_APPS:
        scanned, relevant = pull_play_keep_relevant(app_id, target)
        play_scanned += scanned
        play_kept += len(relevant)
        kept.extend(relevant)
        print(f"PLAY {app_id} scanned={scanned} kept_relevant={len(relevant)}", flush=True)

    token = _resolve_apify_token(settings)
    apify_scanned = 0
    apify_kept = 0
    if token:
        print("APIFY starting volume run (this can take several minutes)…", flush=True)
        try:
            apify_scanned, apify_records = pull_apify_volume(token, settings.apify_reddit_actor)
            apify_kept = len(apify_records)
            kept.extend(apify_records)
            print(f"APIFY scanned={apify_scanned} kept_relevant={apify_kept}", flush=True)
        except Exception as exc:
            logger.exception("Apify volume run failed: %s", type(exc).__name__)
            print(f"APIFY failed: {type(exc).__name__}", flush=True)
    else:
        print("APIFY skipped (no token)", flush=True)

    unique = list({row.source_ref: row for row in kept}.values())
    print(
        f"UNIQUE_RELEVANT={len(unique)} play_scanned={play_scanned} play_kept={play_kept} "
        f"apify_scanned={apify_scanned} apify_kept={apify_kept}",
        flush=True,
    )
    if unique:
        merge = merge_wishlist_docs(
            Path(settings.scraped_json_path),
            _records_to_docs(unique, run_version),
            run_version,
        )
        print(
            f"CORPUS docs={merge['documents']} chunks={merge['chunks']} "
            f"added={merge['added']} replaced={merge['replaced']} by_source={merge['by_source']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
