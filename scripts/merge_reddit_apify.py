"""Fetch live Reddit wishlist posts via Apify and merge into scraped_corpus.json.

Does not wipe other sources. If Apify returns no relevant posts, existing
Reddit documents are left unchanged.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from ingestion.connectors.reddit import fetch_reddit_records
from ingestion.pipeline import _default_run_version, _serialize_chunk, _serialize_record
from ingestion.stages.chunk import chunk_records
from ingestion.stages.clean import clean_records
from ingestion.stages.dedupe import dedupe_records
from ingestion.stages.enrich import enrich_chunks
from ingestion.stages.pii import scrub_records


def _records_to_docs(records: list, run_version: str) -> list[dict]:
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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    token = settings.apify_api_token
    print(f"apify_token_present={bool(token)} actor={settings.apify_reddit_actor}")

    records = fetch_reddit_records(use_live=True)
    via = {r.metadata.get("via") for r in records}
    print(f"fetched_relevant={len(records)} via={sorted(v for v in via if v)}")
    for rec in records[:12]:
        title = rec.text.splitlines()[0][:120].encode("ascii", "replace").decode("ascii")
        print(f"  - r/{rec.metadata.get('subreddit')}: {title}")

    if not records:
        print("No relevant Reddit posts returned; corpus unchanged.")
        return 0
    if via == {None} or not any(r.metadata.get("via") == "apify" for r in records):
        print("Results are not from Apify; leaving existing Reddit corpus as-is.")
        return 0

    path = Path(settings.scraped_json_path)
    existing = json.loads(path.read_text(encoding="utf-8"))
    kept = [d for d in existing.get("documents", []) if d.get("source") != "reddit"]
    new_docs = _records_to_docs(records, _default_run_version())
    documents = kept + new_docs
    by_source = dict(Counter(d.get("source") for d in documents))
    chunks = sum(len(d.get("chunks") or []) for d in documents)
    existing["documents"] = documents
    existing["exported_at"] = datetime.now(UTC).isoformat()
    existing["run_version"] = new_docs[0]["run_version"] if new_docs else existing.get("run_version")
    stats = existing.setdefault("stats", {})
    stats["documents"] = len(documents)
    stats["chunks"] = chunks
    stats["by_source"] = by_source
    stats["after_filter"] = len(documents)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"merged corpus: docs={len(documents)} chunks={chunks} reddit={by_source.get('reddit', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
