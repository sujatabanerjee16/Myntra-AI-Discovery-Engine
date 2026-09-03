"""Vector retrieval with metadata filtering (pgvector + PostgreSQL)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from common.cache import get_cached_retrieval, retrieval_cache_key, set_cached_retrieval
from common.config import get_settings
from common.models import Chunk, Document, SourceType
from storage.schemas import RetrievalFilters, RetrievedChunk


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    embedding: list[float]
    top_k: int
    filters: RetrievalFilters | None = None


def apply_retrieval_filters(
    stmt: Select,
    filters: RetrievalFilters | None,
) -> Select:
    """Apply metadata filters to a chunk+document retrieval query."""
    if filters is None:
        return stmt

    if filters.source is not None:
        stmt = stmt.where(Document.source == filters.source)
    if filters.sources:
        allowed: list[SourceType] = []
        for raw in filters.sources:
            try:
                allowed.append(SourceType(str(raw)))
            except ValueError:
                continue
        if allowed:
            stmt = stmt.where(Document.source.in_(allowed))
    if filters.category is not None:
        stmt = stmt.where(Chunk.category == filters.category)
    if filters.occasion is not None:
        stmt = stmt.where(Chunk.occasion == filters.occasion)
    if filters.price_band is not None:
        stmt = stmt.where(Chunk.price_band == filters.price_band)
    if filters.segment is not None:
        stmt = stmt.where(Chunk.segment == filters.segment)
    if filters.min_quality_score is not None:
        stmt = stmt.where(Chunk.quality_score >= filters.min_quality_score)
    if filters.signals:
        stmt = stmt.where(Chunk.matched_signals.overlap(filters.signals))

    return stmt


def build_retrieval_statement(query: RetrievalQuery) -> Select:
    """Build a pgvector cosine-distance query with optional metadata filters."""
    distance = Chunk.embedding.cosine_distance(query.embedding).label("distance")

    stmt = (
        select(
            Chunk,
            Document,
            distance,
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance)
        .limit(query.top_k)
    )
    return apply_retrieval_filters(stmt, query.filters)


def search_by_embedding(
    session: Session,
    *,
    query_embedding: list[float],
    top_k: int,
    filters: RetrievalFilters | None = None,
) -> list[RetrievedChunk]:
    """Run pgvector similarity search for a precomputed embedding."""
    stmt = build_retrieval_statement(
        RetrievalQuery(embedding=query_embedding, top_k=top_k, filters=filters)
    )
    rows = session.execute(stmt).all()
    return _rows_to_chunks(rows)


def search_chunks(
    session: Session,
    *,
    query_text: str | None = None,
    query_embedding: list[float] | None = None,
    top_k: int = 8,
    filters: RetrievalFilters | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks via the configured vector backend."""
    settings = get_settings()
    if query_text and settings.retrieval_cache_enabled:
        cache_key = retrieval_cache_key(
            query_text=query_text,
            top_k=top_k,
            filters=filters.model_dump(exclude_none=True) if filters else None,
        )
        cached = get_cached_retrieval(cache_key)
        if cached is not None:
            return [RetrievedChunk.model_validate(item) for item in cached]

    from storage.vector_backend import get_vector_backend

    if query_embedding is not None:
        results = search_by_embedding(
            session,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )
    else:
        if not query_text:
            raise ValueError("Either query_text or query_embedding is required")
        results = get_vector_backend().search(
            session,
            query_text=query_text,
            top_k=top_k,
            filters=filters,
        )

    if query_text and settings.retrieval_cache_enabled:
        cache_key = retrieval_cache_key(
            query_text=query_text,
            top_k=top_k,
            filters=filters.model_dump(exclude_none=True) if filters else None,
        )
        set_cached_retrieval(
            cache_key,
            [item.model_dump(mode="json") for item in results],
        )

    return results


def _rows_to_chunks(rows) -> list[RetrievedChunk]:
    results: list[RetrievedChunk] = []
    for chunk, document, distance in rows:
        score = max(0.0, 1.0 - float(distance))
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=round(score, 4),
                source=document.source,
                source_ref=document.source_ref,
                category=chunk.category,
                occasion=chunk.occasion,
                price_band=chunk.price_band,
                segment=chunk.segment,
                matched_signals=chunk.matched_signals or [],
                quality_score=chunk.quality_score,
                document_created_at=document.created_at,
            )
        )
    return results
