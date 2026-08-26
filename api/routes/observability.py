"""Observability HTTP routes for quality, traces, and cost metrics."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import backend
from api.json_store import json_data_available, load_insights_payload
from common.cache import get_cost_control_snapshot
from common.config import get_settings
from common.db import get_session
from common.models import AnswerTrace, EvalRun, PipelineRun
from eval.runner import run_evaluation, write_eval_report

router = APIRouter(prefix="/observability", tags=["observability"])


class PipelineRunRecord(BaseModel):
    id: uuid.UUID
    run_type: str
    run_version: str
    success: bool
    duration_ms: float | None
    stats: dict[str, Any] | None
    error_message: str | None
    created_at: datetime


class PipelineRunListResponse(BaseModel):
    total: int
    runs: list[PipelineRunRecord]


class EvalRunRecord(BaseModel):
    id: uuid.UUID
    run_version: str
    retrieval_hit_at_k: float | None
    retrieval_mrr: float | None
    faithfulness_score: float | None
    taxonomy_accuracy: float | None
    passed: bool
    created_at: datetime


class EvalRunListResponse(BaseModel):
    total: int
    runs: list[EvalRunRecord]


class EvalSummaryResponse(BaseModel):
    latest: EvalRunRecord | None
    targets: dict[str, float]
    thresholds: dict[str, float]
    cost_controls: dict[str, Any]


class QualityDashboardResponse(BaseModel):
    eval_summary: EvalSummaryResponse
    recent_traces: list[dict[str, Any]]
    recent_pipeline_runs: list[PipelineRunRecord]
    corpus_stats: dict[str, Any] = Field(default_factory=dict)


@router.get("/cost-controls")
def get_cost_controls() -> dict[str, Any]:
    """Return embedding and retrieval cache hit/miss statistics."""
    settings = get_settings()
    return {
        "enabled": {
            "embedding_cache": settings.embedding_cache_enabled,
            "retrieval_cache": settings.retrieval_cache_enabled,
        },
        "caches": get_cost_control_snapshot().to_dict(),
    }


@router.get("/pipeline-runs", response_model=PipelineRunListResponse)
def list_pipeline_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> PipelineRunListResponse:
    total = session.scalar(select(func.count()).select_from(PipelineRun)) or 0
    rows = session.execute(
        select(PipelineRun).order_by(PipelineRun.created_at.desc()).offset(offset).limit(limit)
    ).scalars()

    runs = [
        PipelineRunRecord(
            id=row.id,
            run_type=row.run_type,
            run_version=row.run_version,
            success=row.success,
            duration_ms=row.duration_ms,
            stats=row.stats,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return PipelineRunListResponse(total=total, runs=runs)


@router.get("/eval-runs", response_model=EvalRunListResponse)
def list_eval_runs(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> EvalRunListResponse:
    total = session.scalar(select(func.count()).select_from(EvalRun)) or 0
    rows = session.execute(
        select(EvalRun).order_by(EvalRun.created_at.desc()).offset(offset).limit(limit)
    ).scalars()

    runs = [
        EvalRunRecord(
            id=row.id,
            run_version=row.run_version,
            retrieval_hit_at_k=row.retrieval_hit_at_k,
            retrieval_mrr=row.retrieval_mrr,
            faithfulness_score=row.faithfulness_score,
            taxonomy_accuracy=row.taxonomy_accuracy,
            passed=row.passed,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return EvalRunListResponse(total=total, runs=runs)


@router.get("/eval/latest", response_model=EvalSummaryResponse)
def latest_eval_summary(session: Session = Depends(get_session)) -> EvalSummaryResponse:
    from sqlalchemy.exc import SQLAlchemyError

    settings = get_settings()

    latest = None
    try:
        row = session.execute(
            select(EvalRun).order_by(EvalRun.created_at.desc()).limit(1)
        ).scalar_one_or_none()

        if row is not None:
            latest = EvalRunRecord(
                id=row.id,
                run_version=row.run_version,
                retrieval_hit_at_k=row.retrieval_hit_at_k,
                retrieval_mrr=row.retrieval_mrr,
                faithfulness_score=row.faithfulness_score,
                taxonomy_accuracy=row.taxonomy_accuracy,
                passed=row.passed,
                created_at=row.created_at,
            )
    except SQLAlchemyError:
        pass

    return EvalSummaryResponse(
        latest=latest,
        targets={
            "retrieval_hit": settings.eval_retrieval_hit_target,
            "faithfulness": settings.eval_faithfulness_target,
            "taxonomy_accuracy": settings.eval_taxonomy_accuracy_target,
        },
        thresholds={
            "rag_min_top_score": settings.rag_min_top_score,
            "rag_min_avg_score": settings.rag_min_avg_score,
        },
        cost_controls=get_cost_control_snapshot().to_dict(),
    )


@router.post("/eval/run")
def trigger_eval_run(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Run the evaluation suite and persist results."""
    from api import backend

    persist_db = not backend.use_json_backend()
    report = run_evaluation(session, persist=persist_db)
    output = write_eval_report(report)
    return {"passed": report.passed, "run_version": report.run_version, "report_path": str(output)}


@router.get("/quality", response_model=QualityDashboardResponse)
def quality_dashboard(session: Session = Depends(get_session)) -> QualityDashboardResponse:
    """Combined quality, trace, and cost dashboard payload."""
    from sqlalchemy.exc import SQLAlchemyError

    from common.db import database_available

    corpus_stats: dict[str, Any] = {}
    if json_data_available():
        from pathlib import Path

        settings = get_settings()
        insights = load_insights_payload()
        scraped_path = Path(settings.scraped_json_path)
        document_count = 0
        run_version = None
        if scraped_path.is_file():
            import json

            scraped = json.loads(scraped_path.read_text(encoding="utf-8"))
            document_count = len(scraped.get("documents", []))
            run_version = scraped.get("run_version")
        corpus_stats = {
            "documents": document_count,
            "run_version": run_version,
            "insights_run_version": insights.get("run_version"),
            "backend": "json" if backend.use_json_backend() else "postgres",
        }

    if not database_available():
        return QualityDashboardResponse(
            eval_summary=EvalSummaryResponse(
                latest=None,
                targets={
                    "retrieval_hit": get_settings().eval_retrieval_hit_target,
                    "faithfulness": get_settings().eval_faithfulness_target,
                    "taxonomy_accuracy": get_settings().eval_taxonomy_accuracy_target,
                },
                thresholds={
                    "rag_min_top_score": get_settings().rag_min_top_score,
                    "rag_min_avg_score": get_settings().rag_min_avg_score,
                },
                cost_controls=get_cost_control_snapshot().to_dict(),
            ),
            recent_traces=[],
            recent_pipeline_runs=[],
            corpus_stats=corpus_stats,
        )

    try:
        eval_summary = latest_eval_summary(session)

        trace_rows = session.execute(
            select(AnswerTrace).order_by(AnswerTrace.created_at.desc()).limit(10)
        ).scalars()
        recent_traces = [
            {
                "id": str(row.id),
                "question": row.question[:120],
                "confidence": row.confidence,
                "insufficient_evidence": row.insufficient_evidence,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at.isoformat(),
            }
            for row in trace_rows
        ]

        pipeline_resp = list_pipeline_runs(limit=10, offset=0, session=session)
    except SQLAlchemyError:
        eval_summary = EvalSummaryResponse(
            latest=None,
            targets={
                "retrieval_hit": get_settings().eval_retrieval_hit_target,
                "faithfulness": get_settings().eval_faithfulness_target,
                "taxonomy_accuracy": get_settings().eval_taxonomy_accuracy_target,
            },
            thresholds={
                "rag_min_top_score": get_settings().rag_min_top_score,
                "rag_min_avg_score": get_settings().rag_min_avg_score,
            },
            cost_controls=get_cost_control_snapshot().to_dict(),
        )
        recent_traces = []
        pipeline_resp = PipelineRunListResponse(total=0, runs=[])

    return QualityDashboardResponse(
        eval_summary=eval_summary,
        recent_traces=recent_traces,
        recent_pipeline_runs=pipeline_resp.runs,
        corpus_stats=corpus_stats,
    )


@router.get("/traces/{trace_id}")
def get_observability_trace(
    trace_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(AnswerTrace, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="AnswerTrace not found")
    return {
        "id": str(row.id),
        "question": row.question,
        "answer": row.answer,
        "citations": row.citations or [],
        "confidence": row.confidence,
        "limitations": row.limitations,
        "retrieved_chunk_ids": [str(item) for item in (row.retrieved_chunk_ids or [])],
        "duration_ms": row.duration_ms,
        "insufficient_evidence": row.insufficient_evidence,
        "created_at": row.created_at.isoformat(),
    }
