"""Split documents into retrieval-friendly chunks."""

from __future__ import annotations

from dataclasses import dataclass

from common.config import get_settings
from ingestion.schemas import RawRecord


@dataclass(slots=True)
class TextChunk:
    document_ref: str
    chunk_index: int
    text: str
    matched_signals: list[str]
    metadata: dict


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_records(records: list[RawRecord]) -> list[TextChunk]:
    settings = get_settings()
    out: list[TextChunk] = []

    for record in records:
        parts = _split_text(record.text, settings.chunk_size, settings.chunk_overlap)
        for i, part in enumerate(parts):
            out.append(
                TextChunk(
                    document_ref=record.source_ref,
                    chunk_index=i,
                    text=part,
                    matched_signals=record.matched_signals,
                    metadata=dict(record.metadata),
                )
            )
    return out
