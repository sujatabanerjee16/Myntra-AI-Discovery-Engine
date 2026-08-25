"""Merge competitive seeds into scraped corpus and refresh insights JSON."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from analytics.pipeline import _load_chunks_from_json, export_analytics_json, run_semantic_analytics

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "scraped_corpus.json"
SEED_PATH = ROOT / "data" / "seeds" / "competitive_wishlist.json"
INSIGHTS_PATH = ROOT / "data" / "insights.json"


def _seed_to_documents(seeds: list[dict]) -> list[dict]:
    docs: list[dict] = []
    for seed in seeds:
        source_ref = seed["source_ref"]
        if source_ref.startswith("reddit:"):
            source = "reddit"
        elif source_ref.startswith("youtube:"):
            source = "youtube"
        elif source_ref.startswith("play_store:"):
            source = "play_store"
        elif source_ref.startswith("social:"):
            source = "social"
        elif source_ref.startswith("product_review:"):
            source = "product_review"
        else:
            source = "research"

        platforms = (seed.get("metadata") or {}).get("platforms") or []
        signals = ["wishlist_usage", "external_comparison_seeking", "purchase_hesitation"]
        if any(p in {"nykaa", "ajio", "other"} for p in platforms):
            signals.append("external_comparison_seeking")

        text = seed["text"]
        docs.append(
            {
                "source": source,
                "source_ref": source_ref,
                "text": text,
                "language": seed.get("language", "en"),
                "created_at": seed.get("created_at"),
                "matched_signals": signals,
                "metadata": seed.get("metadata") or {},
                "chunks": [
                    {
                        "chunk_index": 0,
                        "text": text,
                        "matched_signals": signals,
                        "category": "beauty"
                        if "nykaa" in platforms and "beauty" in text.lower()
                        else "clothing",
                        "occasion": "wedding" if "wedding" in text.lower() else None,
                        "price_band": "budget" if "ajio" in platforms else None,
                        "segment": None,
                        "quality_score": 0.82,
                    }
                ],
            }
        )
    return docs


def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    seeds = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    new_docs = _seed_to_documents(seeds)

    existing_refs = {d.get("source_ref") for d in corpus.get("documents", [])}
    added = 0
    for doc in new_docs:
        if doc["source_ref"] in existing_refs:
            # Replace existing competitive seed docs so re-runs stay idempotent.
            corpus["documents"] = [d for d in corpus["documents"] if d.get("source_ref") != doc["source_ref"]]
        corpus["documents"].append(doc)
        added += 1
        existing_refs.add(doc["source_ref"])

    chunk_count = sum(len(d.get("chunks") or []) for d in corpus["documents"])
    by_source: dict[str, int] = {}
    for d in corpus["documents"]:
        by_source[d["source"]] = by_source.get(d["source"], 0) + 1

    corpus["run_version"] = datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")
    corpus["stats"] = {
        "documents": len(corpus["documents"]),
        "chunks": chunk_count,
        "by_source": by_source,
        "competitive_docs_merged": added,
    }
    sources = sorted({d["source"] for d in corpus["documents"]})
    corpus["sources"] = sources

    CORPUS_PATH.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated corpus: {CORPUS_PATH} ({len(corpus['documents'])} docs, {chunk_count} chunks)")

    raw = _load_chunks_from_json(CORPUS_PATH)
    result = run_semantic_analytics(raw)
    export_analytics_json(result, INSIGHTS_PATH)
    print(
        f"Exported insights: {INSIGHTS_PATH} "
        f"(competitive_aggregates={result.competitive_aggregates})"
    )


if __name__ == "__main__":
    main()
