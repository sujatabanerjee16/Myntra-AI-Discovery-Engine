"""Keyword retrieval fallback when PostgreSQL is unavailable."""

from __future__ import annotations

import re

from api.json_store import load_corpus_chunks
from common.models import SourceType
from storage.schemas import RetrievedChunk, RetrievalFilters


def _keyword_overlap(query: str, text: str) -> float:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2 and token not in {"the", "and", "for", "what", "why", "how", "when"}
    }
    if not tokens:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for token in tokens if token in text_lower)
    return hits / len(tokens)


def _matches_filters(chunk: dict, filters: RetrievalFilters | None) -> bool:
    if filters is None:
        return True
    if filters.source is not None and chunk["source"] != filters.source.value:
        return False
    if filters.category is not None and chunk.get("category") != filters.category:
        return False
    if filters.occasion is not None and chunk.get("occasion") != filters.occasion:
        return False
    if filters.price_band is not None and chunk.get("price_band") != filters.price_band:
        return False
    if filters.segment is not None and chunk.get("segment") != filters.segment:
        return False
    if filters.min_quality_score is not None:
        quality = chunk.get("quality_score") or 0.0
        if quality < filters.min_quality_score:
            return False
    if filters.signals:
        signals = set(chunk.get("matched_signals") or [])
        if not signals.intersection(filters.signals):
            return False
    return True


def search_chunks_json(
    *,
    query_text: str,
    top_k: int = 8,
    filters: RetrievalFilters | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks from the local JSON corpus using keyword overlap."""
    scored: list[tuple[float, dict]] = []
    for chunk in load_corpus_chunks():
        if not _matches_filters(chunk, filters):
            continue
        overlap = _keyword_overlap(query_text, chunk["text"])
        quality = float(chunk.get("quality_score") or 0.5)
        score = (0.7 * overlap) + (0.3 * quality)
        if score <= 0:
            continue
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[RetrievedChunk] = []
    for score, chunk in scored[:top_k]:
        results.append(
            RetrievedChunk(
                chunk_id=chunk["chunk_id"],
                document_id=chunk["document_id"],
                chunk_index=chunk.get("chunk_index", 0),
                text=chunk["text"],
                score=round(score, 4),
                source=SourceType(chunk["source"]),
                source_ref=chunk.get("source_ref"),
                category=chunk.get("category"),
                occasion=chunk.get("occasion"),
                price_band=chunk.get("price_band"),
                segment=chunk.get("segment"),
                matched_signals=chunk.get("matched_signals") or [],
                quality_score=chunk.get("quality_score"),
                document_created_at=None,
            )
        )
    return results
