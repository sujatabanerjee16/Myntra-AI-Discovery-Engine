"""Rerank retrieved chunks for relevance to the user question."""

from __future__ import annotations

import re

from storage.schemas import RetrievedChunk


def _keyword_overlap(question: str, text: str) -> float:
    question_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", question.lower())
        if len(token) > 2 and token not in {"the", "and", "for", "what", "why", "how", "when"}
    }
    if not question_tokens:
        return 0.0

    text_lower = text.lower()
    hits = sum(1 for token in question_tokens if token in text_lower)
    return hits / len(question_tokens)


def rerank_chunks(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int,
) -> list[RetrievedChunk]:
    """Combine vector score, quality, and lexical overlap for final ordering."""
    if not chunks:
        return []

    scored: list[tuple[float, RetrievedChunk]] = []
    for chunk in chunks:
        quality = chunk.quality_score if chunk.quality_score is not None else 0.5
        overlap = _keyword_overlap(question, chunk.text)
        combined = (0.55 * chunk.score) + (0.2 * quality) + (0.25 * overlap)
        scored.append((combined, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    reranked: list[RetrievedChunk] = []
    for combined, chunk in scored[:top_k]:
        reranked.append(
            chunk.model_copy(update={"score": round(combined, 4)})
        )
    return reranked
