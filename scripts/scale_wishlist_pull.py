"""Larger Play Store + Reddit + YouTube pull; keep only real wishlist rows.

Merges new wishlist_usage documents into data/scraped_corpus.json by source_ref.
Does not wipe research or other sources.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.play_store import _author_hash as play_author_hash
from ingestion.connectors.reddit import (
    _USER_AGENT,
    _apify_headers,
    _apify_item_to_record,
    _author_hash as reddit_author_hash,
    _resolve_apify_token,
    _run_apify_actor,
)
from ingestion.connectors.youtube import _fetch_live_records as youtube_live
from ingestion.filters.relevance import is_relevant
from ingestion.pipeline import _default_run_version, _serialize_chunk, _serialize_record
from ingestion.schemas import RawRecord
from ingestion.stages.chunk import chunk_records
from ingestion.stages.clean import clean_records
from ingestion.stages.dedupe import dedupe_records
from ingestion.stages.enrich import enrich_chunks
from ingestion.stages.pii import scrub_records

logger = logging.getLogger(__name__)

REDDIT_QUERIES = (
    "myntra wishlist",
    "ajio wishlist",
    "nykaa wishlist",
    "myntra wish list",
    "myntra \"save for later\"",
    "myntra shortlist",
    "wishlist sale myntra",
    "myntra bookmark cart",
)

PLAY_TARGET = 2000
PLAY_PAGE = 200
REDDIT_PAGES_PER_QUERY = 2
REDDIT_PAGE_SIZE = 100
APIFY_MAX_ITEMS = 50
YOUTUBE_VIDEO_LIMIT = 15
YOUTUBE_COMMENT_LIMIT = 50


def _wishlist_only(records: list[RawRecord]) -> list[RawRecord]:
    return [row for row in records if "wishlist_usage" in (row.matched_signals or [])]


def _records_to_docs(records: list[RawRecord], run_version: str) -> list[dict]:
    cleaned = clean_records(records)
    scrubbed = scrub_records(cleaned)
    deduped = dedupe_records(scrubbed)
    docs: list[dict] = []
    for record in deduped:
        enriched = enrich_chunks(chunk_records([record]))
        doc = _serialize_record(record, run_version)
        doc["chunks"] = [_serialize_chunk(item, None) for item in enriched]
        docs.append(doc)
    return docs


def pull_play_store(app_id: str, target: int = PLAY_TARGET) -> tuple[int, list[RawRecord], list[RawRecord]]:
    try:
        from google_play_scraper import Sort, reviews
    except ImportError:
        logger.exception("google_play_scraper is not installed")
        return 0, [], []

    scanned = 0
    relevant: list[RawRecord] = []
    token = None
    while scanned < target:
        kwargs = {
            "lang": "en",
            "country": "in",
            "sort": Sort.NEWEST,
            "count": min(PLAY_PAGE, target - scanned),
        }
        if token is not None:
            kwargs["continuation_token"] = token
        batch, token = reviews(app_id, **kwargs)
        if not batch:
            break
        for review in batch:
            content = (review.get("content") or "").strip()
            if not content:
                continue
            scanned += 1
            relevance = is_relevant(content)
            if not relevance.is_relevant:
                continue
            review_id = str(review.get("reviewId") or content[:40])
            at = review.get("at")
            created_at = (
                at.replace(tzinfo=UTC) if isinstance(at, datetime) and at.tzinfo is None else at
            )
            relevant.append(
                RawRecord(
                    source=SourceType.play_store,
                    source_ref=f"play_store:{app_id}:{review_id}",
                    text=content,
                    author_hash=play_author_hash(review_id),
                    language="en",
                    created_at=created_at,
                    metadata={
                        "score": review.get("score"),
                        "thumbs_up": review.get("thumbsUpCount"),
                        "app_id": app_id,
                        "platform": "android_play_store",
                        "via": "scale_pull",
                    },
                    matched_signals=list(relevance.matched_signals),
                )
            )
        logger.info("Play Store scanned=%s relevant=%s", scanned, len(relevant))
        if token is None:
            break
        time.sleep(0.4)
    return scanned, relevant, _wishlist_only(relevant)


def pull_reddit_public() -> tuple[int, list[RawRecord], list[RawRecord]]:
    import httpx

    scanned = 0
    relevant: list[RawRecord] = []
    seen_refs: set[str] = set()
    with httpx.Client(timeout=25.0, headers={"User-Agent": _USER_AGENT}) as client:
        for query in REDDIT_QUERIES:
            after = None
            for _page in range(REDDIT_PAGES_PER_QUERY):
                params = {
                    "q": query,
                    "sort": "new",
                    "limit": REDDIT_PAGE_SIZE,
                    "type": "link",
                    "restrict_sr": "false",
                }
                if after:
                    params["after"] = after
                response = client.get("https://www.reddit.com/search.json", params=params)
                if response.status_code in {401, 403, 429}:
                    logger.warning(
                        "Reddit public search HTTP %s; stopping public pull",
                        response.status_code,
                    )
                    return scanned, relevant, _wishlist_only(relevant)
                response.raise_for_status()
                payload = response.json().get("data") or {}
                children = payload.get("children") or []
                after = payload.get("after")
                for child in children:
                    post = child.get("data") or {}
                    title = (post.get("title") or "").strip()
                    body = (post.get("selftext") or "").strip()
                    text = f"{title}\n\n{body}".strip() if body else title
                    if not text:
                        continue
                    scanned += 1
                    relevance = is_relevant(text)
                    if not relevance.is_relevant:
                        continue
                    post_id = post.get("id") or post.get("name") or text[:40]
                    source_ref = f"reddit:{post.get('subreddit', 'unknown')}:{post_id}"
                    if source_ref in seen_refs:
                        continue
                    seen_refs.add(source_ref)
                    created = post.get("created_utc")
                    created_at = (
                        datetime.fromtimestamp(float(created), tz=UTC) if created is not None else None
                    )
                    relevant.append(
                        RawRecord(
                            source=SourceType.reddit,
                            source_ref=source_ref,
                            text=text,
                            author_hash=reddit_author_hash(str(post.get("author") or post_id)),
                            language="en",
                            created_at=created_at,
                            metadata={
                                "subreddit": post.get("subreddit"),
                                "permalink": post.get("permalink"),
                                "score": post.get("score"),
                                "query": query,
                                "via": "reddit_public",
                            },
                            matched_signals=list(relevance.matched_signals),
                        )
                    )
                logger.info(
                    "Reddit query=%r page kept_relevant=%s scanned=%s",
                    query,
                    len(relevant),
                    scanned,
                )
                if not after or not children:
                    break
                time.sleep(1.2)
    return scanned, relevant, _wishlist_only(relevant)


def pull_reddit_apify(token: str, actor: str) -> tuple[int, list[RawRecord], list[RawRecord]]:
    import httpx

    actor_id = actor.replace("/", "~")
    headers = _apify_headers(token)
    relevant: list[RawRecord] = []
    scanned = 0
    with httpx.Client(timeout=45.0) as client:
        for query in REDDIT_QUERIES[:2]:
            payload = {
                "searches": [query],
                "searchPosts": True,
                "searchComments": False,
                "searchCommunities": False,
                "searchUsers": False,
                "skipComments": True,
                "maxItems": APIFY_MAX_ITEMS,
                "maxPostCount": APIFY_MAX_ITEMS,
                "maxComments": 0,
                "sort": "relevance",
                "time": "all",
                "proxy": {"useApifyProxy": True},
            }
            try:
                items = _run_apify_actor(client, actor_id, headers, payload)
            except Exception:
                logger.exception("Apify query failed: %s", query)
                continue
            if not isinstance(items, list):
                continue
            scanned += len(items)
            for item in items:
                if not isinstance(item, dict):
                    continue
                record = _apify_item_to_record(item)
                if record is None:
                    continue
                record.metadata["query"] = query
                relevant.append(record)
            logger.info("Apify query=%r items=%s wishlist_so_far=%s", query, len(items), len(relevant))
    return scanned, relevant, _wishlist_only(relevant)


def pull_youtube(api_key: str) -> tuple[int, list[RawRecord], list[RawRecord]]:
    records = youtube_live(
        query="myntra wishlist OR ajio wishlist OR nykaa wishlist",
        limit=YOUTUBE_COMMENT_LIMIT,
        api_key=api_key,
    )
    # youtube_live already relevance-filters; scanned count is not returned, use kept as proxy
    return len(records), records, _wishlist_only(records)


def merge_wishlist_docs(path: Path, new_docs: list[dict], run_version: str) -> dict:
    existing = json.loads(path.read_text(encoding="utf-8"))
    documents = list(existing.get("documents") or [])
    by_ref = {doc.get("source_ref"): i for i, doc in enumerate(documents) if doc.get("source_ref")}
    added = 0
    replaced = 0
    for doc in new_docs:
        ref = doc.get("source_ref")
        if ref and ref in by_ref:
            documents[by_ref[ref]] = doc
            replaced += 1
        else:
            if ref:
                by_ref[ref] = len(documents)
            documents.append(doc)
            added += 1
    by_source = dict(Counter(doc.get("source") for doc in documents))
    chunks = sum(len(doc.get("chunks") or []) for doc in documents)
    existing["documents"] = documents
    existing["exported_at"] = datetime.now(UTC).isoformat()
    existing["run_version"] = run_version
    stats = existing.setdefault("stats", {})
    stats["documents"] = len(documents)
    stats["chunks"] = chunks
    stats["by_source"] = by_source
    stats["after_filter"] = len(documents)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "added": added,
        "replaced": replaced,
        "documents": len(documents),
        "chunks": chunks,
        "by_source": by_source,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    run_version = _default_run_version()
    summary: dict[str, dict] = {}
    wishlist_records: list[RawRecord] = []

    play_scanned, play_rel, play_wish = pull_play_store(settings.myntra_play_store_app_id)
    summary["play_store"] = {
        "scanned": play_scanned,
        "relevant": len(play_rel),
        "wishlist_kept": len(play_wish),
    }
    wishlist_records.extend(play_wish)
    print(
        f"PLAY scanned={play_scanned} relevant={len(play_rel)} wishlist_kept={len(play_wish)}",
        flush=True,
    )

    reddit_scanned, reddit_rel, reddit_wish = pull_reddit_public()
    summary["reddit_public"] = {
        "scanned": reddit_scanned,
        "relevant": len(reddit_rel),
        "wishlist_kept": len(reddit_wish),
    }
    wishlist_records.extend(reddit_wish)
    print(
        f"REDDIT_PUBLIC scanned={reddit_scanned} relevant={len(reddit_rel)} wishlist_kept={len(reddit_wish)}",
        flush=True,
    )

    token = _resolve_apify_token(settings)
    if token:
        apify_scanned, apify_rel, apify_wish = pull_reddit_apify(token, settings.apify_reddit_actor)
        summary["reddit_apify"] = {
            "scanned": apify_scanned,
            "relevant": len(apify_rel),
            "wishlist_kept": len(apify_wish),
        }
        wishlist_records.extend(apify_wish)
        print(
            f"REDDIT_APIFY scanned={apify_scanned} relevant={len(apify_rel)} wishlist_kept={len(apify_wish)}",
            flush=True,
        )
    else:
        summary["reddit_apify"] = {"scanned": 0, "relevant": 0, "wishlist_kept": 0, "note": "no token"}
        print("REDDIT_APIFY skipped (no token)", flush=True)

    if settings.youtube_api_key:
        yt_scanned, yt_rel, yt_wish = pull_youtube(settings.youtube_api_key)
        summary["youtube"] = {
            "scanned": yt_scanned,
            "relevant": len(yt_rel),
            "wishlist_kept": len(yt_wish),
        }
        wishlist_records.extend(yt_wish)
        print(
            f"YOUTUBE relevant={len(yt_rel)} wishlist_kept={len(yt_wish)}",
            flush=True,
        )
    else:
        summary["youtube"] = {
            "scanned": 0,
            "relevant": 0,
            "wishlist_kept": 0,
            "note": "no YOUTUBE_API_KEY",
        }
        print("YOUTUBE skipped (no YOUTUBE_API_KEY)", flush=True)

    # Dedupe wishlist records by source_ref before merge
    unique: dict[str, RawRecord] = {}
    for record in wishlist_records:
        unique[record.source_ref] = record
    kept = list(unique.values())
    print(f"UNIQUE_WISHLIST_ROWS={len(kept)}", flush=True)

    if kept:
        new_docs = _records_to_docs(kept, run_version)
        merge = merge_wishlist_docs(Path(settings.scraped_json_path), new_docs, run_version)
        summary["merge"] = merge
        print(
            f"MERGED added={merge['added']} replaced={merge['replaced']} "
            f"corpus_docs={merge['documents']} chunks={merge['chunks']}",
            flush=True,
        )
    else:
        print("No new wishlist rows; corpus unchanged.", flush=True)

    report_path = ROOT / "data" / "scale_wishlist_pull_report.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"REPORT {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
