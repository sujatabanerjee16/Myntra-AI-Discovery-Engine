"""Document and chunk repository helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.models import Chunk, Document, SourceType


def document_exists(session: Session, source: SourceType, source_ref: str) -> bool:
    stmt = select(Document.id).where(
        Document.source == source,
        Document.source_ref == source_ref,
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def get_storage_stats(session: Session) -> dict:
    doc_count = session.scalar(select(func.count()).select_from(Document)) or 0
    chunk_count = session.scalar(select(func.count()).select_from(Chunk)) or 0
    embedded_count = (
        session.scalar(select(func.count()).select_from(Chunk).where(Chunk.embedding.isnot(None)))
        or 0
    )

    by_source_rows = session.execute(
        select(Document.source, func.count()).group_by(Document.source).order_by(Document.source)
    ).all()
    by_source = {row[0].value: row[1] for row in by_source_rows}

    latest_run = session.scalar(
        select(Document.run_version)
        .where(Document.run_version.isnot(None))
        .order_by(Document.ingested_at.desc())
        .limit(1)
    )

    return {
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "embedded_chunk_count": embedded_count,
        "by_source": by_source,
        "latest_run_version": latest_run,
    }


def list_documents(
    session: Session,
    *,
    source: SourceType | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    count_stmt = select(func.count()).select_from(Document)
    if source is not None:
        count_stmt = count_stmt.where(Document.source == source)
    total = session.scalar(count_stmt) or 0

    list_stmt = select(Document)
    if source is not None:
        list_stmt = list_stmt.where(Document.source == source)

    rows = session.execute(
        list_stmt.order_by(Document.ingested_at.desc()).offset(offset).limit(limit)
    ).scalars()

    summaries: list[dict] = []
    for doc in rows:
        chunk_count = (
            session.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
            )
            or 0
        )
        summaries.append(
            {
                "id": doc.id,
                "source": doc.source,
                "source_ref": doc.source_ref,
                "language": doc.language,
                "created_at": doc.created_at,
                "ingested_at": doc.ingested_at,
                "run_version": doc.run_version,
                "chunk_count": chunk_count,
                "text_preview": doc.text[:200],
            }
        )
    return total, summaries


def create_document(
    session: Session,
    *,
    source: SourceType,
    source_ref: str,
    text: str,
    run_version: str,
    author_hash: str | None = None,
    language: str | None = None,
    created_at: datetime | None = None,
) -> Document:
    doc = Document(
        source=source,
        source_ref=source_ref,
        text=text,
        author_hash=author_hash,
        language=language,
        created_at=created_at,
        run_version=run_version,
    )
    session.add(doc)
    session.flush()
    return doc


def create_chunk(
    session: Session,
    *,
    document_id: uuid.UUID,
    text: str,
    embedding: list[float] | None,
    chunk_index: int = 0,
    matched_signals: list[str] | None = None,
    category: str | None = None,
    occasion: str | None = None,
    price_band: str | None = None,
    segment: str | None = None,
    quality_score: float | None = None,
) -> Chunk:
    chunk = Chunk(
        document_id=document_id,
        text=text,
        embedding=embedding,
        chunk_index=chunk_index,
        matched_signals=matched_signals,
        category=category,
        occasion=occasion,
        price_band=price_band,
        segment=segment,
        quality_score=quality_score,
    )
    session.add(chunk)
    return chunk
