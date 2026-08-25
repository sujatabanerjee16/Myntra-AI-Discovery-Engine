"""Ingestion scale-out HTTP routes."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.config import get_settings
from common.db import get_session
from common.models import SourceRefreshState
from ingestion.connectors.registry import ALL_SOURCES
from ingestion.pipeline import prepare_corpus
from ingestion.scheduler import refresh_interval_for, sources_due_for_refresh, update_refresh_states
from ingestion.validation import summarize_source_coverage

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class SourceRefreshRecord(BaseModel):
    source: str
    last_run_at: datetime | None
    last_success_at: datetime | None
    next_refresh_at: datetime | None
    last_run_version: str | None
    documents_added: int
    success: bool
    refresh_interval_hours: float


class IngestionStatusResponse(BaseModel):
    supported_sources: list[str]
    refresh_states: list[SourceRefreshRecord]
    due_sources: list[str]
    source_coverage: dict[str, bool]


class RefreshRequest(BaseModel):
    sources: list[str] | None = None
    force: bool = False
    skip_embed: bool = False
    skip_analytics: bool = False


@router.get("/sources", response_model=IngestionStatusResponse)
def ingestion_status(session: Session = Depends(get_session)) -> IngestionStatusResponse:
    settings = get_settings()
    rows = session.execute(select(SourceRefreshState).order_by(SourceRefreshState.source)).scalars()
    refresh_states = [
        SourceRefreshRecord(
            source=row.source.value,
            last_run_at=row.last_run_at,
            last_success_at=row.last_success_at,
            next_refresh_at=row.next_refresh_at,
            last_run_version=row.last_run_version,
            documents_added=row.documents_added,
            success=row.success,
            refresh_interval_hours=refresh_interval_for(row.source).total_seconds() / 3600,
        )
        for row in rows
    ]

    due = sources_due_for_refresh(session, sources=list(ALL_SOURCES))

    corpus, _result = prepare_corpus(
        sources=list(ALL_SOURCES),
        research_excel_path=settings.research_excel_path,
        play_store_limit=0,
        skip_embed=True,
    )
    coverage = summarize_source_coverage(Counter(corpus["stats"]["by_source"]))

    return IngestionStatusResponse(
        supported_sources=list(ALL_SOURCES),
        refresh_states=refresh_states,
        due_sources=due,
        source_coverage=coverage,
    )


@router.post("/refresh")
def trigger_refresh(
    body: RefreshRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Run incremental refresh for due sources and optionally recompute analytics."""
    from analytics.pipeline import run_semantic_analytics_db
    from ingestion.pipeline import run_pipeline

    settings = get_settings()
    requested = body.sources or settings.default_source_list
    due = sources_due_for_refresh(session, sources=requested, force=body.force)
    if not due:
        return {"message": "No sources due for refresh", "due_sources": []}

    result = run_pipeline(
        session,
        sources=due,
        research_excel_path=settings.research_excel_path,
        play_store_limit=settings.play_store_review_limit,
        skip_embed=body.skip_embed,
    )
    update_refresh_states(
        session,
        run_version=result.run_version,
        source_stats=result.sources_created or result.sources,
        success=True,
    )
    session.commit()

    analytics_summary: dict[str, Any] | None = None
    if settings.recompute_analytics_on_refresh and not body.skip_analytics:
        analytics = run_semantic_analytics_db(
            session,
            run_version=result.run_version,
            replace_existing=True,
        )
        session.commit()
        analytics_summary = {
            "run_version": analytics.run_version,
            "insights_created": analytics.insights_created,
            "reason_aggregates": analytics.reason_aggregates,
        }

    return {
        "run_version": result.run_version,
        "sources_refreshed": due,
        "documents_created": result.documents_created,
        "documents_skipped": result.documents_skipped,
        "chunks_created": result.chunks_created,
        "by_source": result.sources,
        "validation": result.validation.to_dict() if result.validation else {},
        "analytics": analytics_summary,
    }
