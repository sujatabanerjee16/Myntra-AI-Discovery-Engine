"""Load and cache local JSON corpus + analytics exports for DB-less mode."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from common.config import get_settings

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_data_path(raw: str) -> Path:
    """Resolve a data file path against cwd first, then the repo root."""
    path = Path(raw)
    if path.is_file():
        return path
    candidate = _PROJECT_ROOT / raw
    if candidate.is_file():
        return candidate
    bundled = _PROJECT_ROOT / "api" / "bundled_data" / Path(raw).name
    if bundled.is_file():
        return bundled
    return path


def parse_chunk_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


_insights_mtime: float | None = None
_insights_payload: dict[str, Any] | None = None


def load_insights_payload() -> dict[str, Any]:
    """Load insights JSON, refreshing when the file changes on disk."""
    global _insights_mtime, _insights_payload
    settings = get_settings()
    path = resolve_data_path(settings.insights_json_path)
    if not path.is_file():
        return {
            "run_version": None,
            "insights": [],
            "reasons": [],
            "clusters": [],
        }
    mtime = path.stat().st_mtime
    if _insights_payload is not None and _insights_mtime == mtime:
        return _insights_payload
    _insights_payload = json.loads(path.read_text(encoding="utf-8"))
    _insights_mtime = mtime
    return _insights_payload


_corpus_mtime: float | None = None
_corpus_chunks: list[dict[str, Any]] | None = None


def load_corpus_chunks() -> list[dict[str, Any]]:
    """Load corpus chunks, refreshing when the export changes on disk."""
    global _corpus_mtime, _corpus_chunks
    settings = get_settings()
    path = resolve_data_path(settings.scraped_json_path)
    if not path.is_file():
        return []
    mtime = path.stat().st_mtime
    if _corpus_chunks is not None and _corpus_mtime == mtime:
        return _corpus_chunks

    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[dict[str, Any]] = []
    for doc in payload.get("documents", []):
        source = doc["source"]
        if hasattr(source, "value"):
            source = source.value
        source_ref = doc.get("source_ref")
        metadata = doc.get("metadata") or {}
        for chunk in doc.get("chunks", []):
            chunk_index = chunk.get("chunk_index", 0)
            chunk_key = f"{source_ref}:{chunk_index}"
            chunk_meta = chunk.get("metadata") or metadata
            segment = chunk.get("segment") or chunk_meta.get("age_band")
            chunks.append(
                {
                    "chunk_id": parse_chunk_uuid(chunk_key),
                    "document_id": parse_chunk_uuid(str(source_ref)),
                    "chunk_index": chunk_index,
                    "text": chunk["text"],
                    "source": source,
                    "source_ref": source_ref,
                    "category": chunk.get("category"),
                    "occasion": chunk.get("occasion"),
                    "price_band": chunk.get("price_band"),
                    "segment": segment,
                    "quality_score": chunk.get("quality_score"),
                    "matched_signals": chunk.get("matched_signals")
                    or doc.get("matched_signals")
                    or [],
                    "metadata": chunk_meta,
                }
            )
    _corpus_chunks = chunks
    _corpus_mtime = mtime
    chunk_lookup.cache_clear()
    return chunks


@lru_cache
def chunk_lookup() -> dict[uuid.UUID, dict[str, Any]]:
    return {item["chunk_id"]: item for item in load_corpus_chunks()}


def json_data_available() -> bool:
    settings = get_settings()
    return resolve_data_path(settings.insights_json_path).is_file()


_scrape_stats_mtime: float | None = None
_scrape_stats_payload: dict[str, Any] | None = None


def load_corpus_scrape_stats() -> dict[str, Any]:
    """Count scraped documents and classified chunks by source from the corpus file."""
    global _scrape_stats_mtime, _scrape_stats_payload
    settings = get_settings()
    path = resolve_data_path(settings.scraped_json_path)
    if not path.is_file():
        return {"documents": 0, "chunks": 0, "by_source": []}
    mtime = path.stat().st_mtime
    if _scrape_stats_payload is not None and _scrape_stats_mtime == mtime:
        return _scrape_stats_payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_docs: dict[str, int] = {}
    by_chunks: dict[str, int] = {}
    workbook_rows: dict[str, set[str]] = {}
    open_text = 0
    interviews = 0
    for doc in payload.get("documents", []):
        source = doc.get("source")
        if hasattr(source, "value"):
            source = source.value
        key = str(source or "unknown")
        by_docs[key] = by_docs.get(key, 0) + 1
        chunk_n = len(doc.get("chunks") or [])
        by_chunks[key] = by_chunks.get(key, 0) + chunk_n
        if key != "research":
            continue
        ref = str(doc.get("source_ref") or "")
        meta = doc.get("metadata") or {}
        if ":open:" in ref:
            open_text += 1
            continue
        if "interview" in ref:
            interviews += 1
            continue
        # Blank / unaged Excel rows are not people (one habits row is all NaT).
        if meta.get("age_band") not in ("age_18_24", "age_25_35"):
            continue
        workbook = str(meta.get("workbook") or "workbook")
        if meta.get("row_index") is not None:
            row_key = f"{workbook}:{meta.get('row_index')}"
        elif ":row:" in ref:
            row_key = ref
        else:
            continue
        workbook_rows.setdefault(workbook, set()).add(row_key)
    by_source = [
        {
            "source": source,
            "documents": by_docs[source],
            "chunks": by_chunks.get(source, 0),
        }
        for source in sorted(by_docs, key=lambda item: by_docs[item], reverse=True)
    ]
    survey_documents = by_docs.get("research", 0)
    scraped_documents = sum(count for source, count in by_docs.items() if source != "research")
    survey_by_workbook = [
        {"workbook": name, "respondents": len(refs)}
        for name, refs in sorted(workbook_rows.items(), key=lambda item: -len(item[1]))
    ]
    survey_respondents = sum(item["respondents"] for item in survey_by_workbook)
    _scrape_stats_payload = {
        "documents": sum(by_docs.values()),
        "chunks": sum(by_chunks.values()),
        "by_source": by_source,
        "survey_documents": survey_documents,
        "scraped_documents": scraped_documents,
        "survey_respondents": survey_respondents,
        "survey_open_text": open_text,
        "survey_interviews": interviews,
        "survey_by_workbook": survey_by_workbook,
    }
    _scrape_stats_mtime = mtime
    return _scrape_stats_payload
