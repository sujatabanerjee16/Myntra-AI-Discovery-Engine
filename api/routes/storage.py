"""Storage layer HTTP routes (stats, documents, aggregates)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import get_session
from common.models import DimensionAggregate, SignalAggregate, SourceAggregate, SourceType
from storage.repository import get_storage_stats, list_documents
from storage.schemas import DocumentListResponse, DocumentSummary, StorageStatsResponse

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/stats", response_model=StorageStatsResponse)
def storage_stats(session: Session = Depends(get_session)) -> StorageStatsResponse:
    """Return counts for documents, chunks, and sources."""
    return StorageStatsResponse(**get_storage_stats(session))


@router.get("/documents", response_model=DocumentListResponse)
def storage_documents(
    source: SourceType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DocumentListResponse:
    """List ingested documents with optional source filter."""
    total, rows = list_documents(session, source=source, limit=limit, offset=offset)
    return DocumentListResponse(
        total=total,
        documents=[DocumentSummary(**row) for row in rows],
    )


@router.get("/aggregates/sources")
def aggregate_sources(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return source-level analytical aggregates for the dashboard."""
    stmt = select(SourceAggregate).order_by(SourceAggregate.source)
    if run_version:
        stmt = stmt.where(SourceAggregate.run_version == run_version)
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "source": row.source.value,
            "document_count": row.document_count,
            "chunk_count": row.chunk_count,
            "avg_quality_score": row.avg_quality_score,
            "run_version": row.run_version,
        }
        for row in rows
    ]


@router.get("/aggregates/signals")
def aggregate_signals(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return priority-signal aggregates (heatmap/ranking inputs)."""
    stmt = select(SignalAggregate).order_by(SignalAggregate.chunk_count.desc())
    if run_version:
        stmt = stmt.where(SignalAggregate.run_version == run_version)
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "signal": row.signal,
            "chunk_count": row.chunk_count,
            "document_count": row.document_count,
            "run_version": row.run_version,
        }
        for row in rows
    ]


@router.get("/aggregates/dimensions")
def aggregate_dimensions(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return segment/category/occasion/price-band heatmap aggregates."""
    stmt = select(DimensionAggregate).order_by(DimensionAggregate.chunk_count.desc())
    if run_version:
        stmt = stmt.where(DimensionAggregate.run_version == run_version)
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "segment": row.segment,
            "category": row.category,
            "occasion": row.occasion,
            "price_band": row.price_band,
            "chunk_count": row.chunk_count,
            "run_version": row.run_version,
        }
        for row in rows
    ]
