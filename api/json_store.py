"""Load and cache local JSON corpus + analytics exports for DB-less mode."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from common.config import get_settings


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
    path = Path(settings.insights_json_path)
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


@lru_cache
def load_corpus_chunks() -> list[dict[str, Any]]:
    settings = get_settings()
    path = Path(settings.scraped_json_path)
    if not path.is_file():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[dict[str, Any]] = []
    for doc in payload.get("documents", []):
        source = doc["source"]
        source_ref = doc.get("source_ref")
        for chunk in doc.get("chunks", []):
            chunk_index = chunk.get("chunk_index", 0)
            chunk_key = f"{source_ref}:{chunk_index}"
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
                    "segment": chunk.get("segment"),
                    "quality_score": chunk.get("quality_score"),
                    "matched_signals": chunk.get("matched_signals") or doc.get("matched_signals") or [],
                }
            )
    return chunks


@lru_cache
def chunk_lookup() -> dict[uuid.UUID, dict[str, Any]]:
    return {item["chunk_id"]: item for item in load_corpus_chunks()}


def json_data_available() -> bool:
    settings = get_settings()
    return Path(settings.insights_json_path).is_file()
