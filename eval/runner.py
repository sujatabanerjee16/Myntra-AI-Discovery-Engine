"""Run the full Phase 6 evaluation suite."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from api import backend
from assistant.guardrails import assess_evidence, build_insufficient_evidence_answer
from assistant.llm import generate_grounded_answer
from assistant.rerank import rerank_chunks
from common.cache import get_cost_control_snapshot
from common.config import get_settings
from common.models import EvalRun
from eval.datasets import (
    default_faithfulness_cases,
    default_retrieval_cases,
    default_taxonomy_cases,
    load_faithfulness_cases,
    load_retrieval_cases,
    load_taxonomy_cases,
)
from eval.faithfulness import compute_faithfulness_metrics, score_answer_faithfulness
from eval.metrics import compute_retrieval_metrics, compute_taxonomy_metrics
from eval.schemas import EvalReport, FaithfulnessEvalCase, MetricResult

logger = logging.getLogger(__name__)


def _default_run_version() -> str:
    return datetime.now(UTC).strftime("eval-%Y%m%dT%H%M%SZ")


def _resolve_retrieval_cases():
    loaded = load_retrieval_cases()
    return loaded or default_retrieval_cases()


def _resolve_taxonomy_cases():
    loaded = load_taxonomy_cases()
    return loaded or default_taxonomy_cases()


def _resolve_faithfulness_cases():
    loaded = load_faithfulness_cases()
    return loaded or default_faithfulness_cases()


def _evaluate_retrieval(session: Session | None) -> tuple[MetricResult, dict[str, list]]:
    settings = get_settings()
    cases = _resolve_retrieval_cases()
    retrieved_by_query: dict[str, list] = {}

    for case in cases:
        if session is not None and not backend.use_json_backend():
            from storage.retrieval import search_chunks

            chunks = search_chunks(session, query_text=case.query, top_k=settings.retrieval_top_k)
        else:
            chunks = backend.search_with_fallback(
                session,
                query_text=case.query,
                top_k=settings.retrieval_top_k,
                filters=None,
            )
        reranked = rerank_chunks(case.query, chunks, top_k=settings.rag_rerank_top_k)
        retrieved_by_query[case.query] = reranked

    metric = compute_retrieval_metrics(
        cases,
        retrieved_by_query,
        k=settings.eval_retrieval_hit_at_k,
        target=settings.eval_retrieval_hit_target,
    )
    return metric, retrieved_by_query


def _evaluate_taxonomy() -> MetricResult:
    settings = get_settings()
    cases = _resolve_taxonomy_cases()
    return compute_taxonomy_metrics(cases, target=settings.eval_taxonomy_accuracy_target)


def _evaluate_faithfulness_static() -> MetricResult:
    settings = get_settings()
    cases = _resolve_faithfulness_cases()
    return compute_faithfulness_metrics(cases, target=settings.eval_faithfulness_target)


def _evaluate_faithfulness_live(
    session: Session | None,
    retrieved_by_query: dict[str, list],
) -> MetricResult:
    """Score live RAG answers against retrieved evidence for key questions."""
    settings = get_settings()
    live_cases: list[FaithfulnessEvalCase] = []

    for query, chunks in retrieved_by_query.items():
        assessment = assess_evidence(chunks)
        if not assessment.sufficient:
            answer = build_insufficient_evidence_answer(query, assessment)
            live_cases.append(
                FaithfulnessEvalCase(
                    question=query,
                    answer=answer,
                    evidence_texts=[chunk.text for chunk in chunks],
                    should_refuse=True,
                )
            )
            continue

        from api.json_dashboard import fetch_relevant_aggregates_json
        from assistant.context import build_grounded_context, fetch_relevant_aggregates

        aggregates = (
            fetch_relevant_aggregates_json([])
            if backend.use_json_backend() or session is None
            else fetch_relevant_aggregates(session, [])
        )
        context = build_grounded_context(chunks, aggregates)
        generated = generate_grounded_answer(query, context, chunks, aggregates)
        live_cases.append(
            FaithfulnessEvalCase(
                question=query,
                answer=generated.answer,
                evidence_texts=[chunk.text for chunk in chunks[:3]],
            )
        )

    if not live_cases:
        return _evaluate_faithfulness_static()

    scores = [
        score_answer_faithfulness(
            case.answer,
            case.evidence_texts,
            should_refuse=case.should_refuse,
        )
        for case in live_cases
    ]
    average = sum(scores) / len(scores)
    static = _evaluate_faithfulness_static()
    combined = round((average + static.value) / 2, 4)

    return MetricResult(
        name="grounding_faithfulness",
        value=combined,
        target=settings.eval_faithfulness_target,
        passed=combined >= settings.eval_faithfulness_target,
        details={
            "live_average": round(average, 4),
            "static_average": static.value,
            "combined": combined,
            "live_cases": len(live_cases),
            "static_cases": static.details.get("cases", 0),
        },
    )


def run_evaluation(
    session: Session | None = None,
    *,
    run_version: str | None = None,
    persist: bool = True,
    include_live_faithfulness: bool = True,
) -> EvalReport:
    """Execute retrieval, taxonomy, and faithfulness evaluation."""
    settings = get_settings()
    run_version = run_version or _default_run_version()

    retrieval_metric, retrieved_by_query = _evaluate_retrieval(session)
    taxonomy_metric = _evaluate_taxonomy()
    if include_live_faithfulness:
        faithfulness_metric = _evaluate_faithfulness_live(session, retrieved_by_query)
    else:
        faithfulness_metric = _evaluate_faithfulness_static()

    passed = (
        retrieval_metric.passed
        and taxonomy_metric.passed
        and faithfulness_metric.passed
    )

    notes: list[str] = []
    if not retrieval_metric.passed:
        notes.append(
            f"Retrieval hit@{settings.eval_retrieval_hit_at_k} "
            f"({retrieval_metric.value:.2f}) below target "
            f"({settings.eval_retrieval_hit_target:.2f})."
        )
    if not taxonomy_metric.passed:
        notes.append(
            f"Taxonomy accuracy ({taxonomy_metric.value:.2f}) below target "
            f"({settings.eval_taxonomy_accuracy_target:.2f})."
        )
    if not faithfulness_metric.passed:
        notes.append(
            f"Faithfulness ({faithfulness_metric.value:.2f}) below target "
            f"({settings.eval_faithfulness_target:.2f})."
        )

    report = EvalReport(
        run_version=run_version,
        created_at=datetime.now(UTC),
        retrieval=retrieval_metric,
        faithfulness=faithfulness_metric,
        taxonomy=taxonomy_metric,
        cost_controls=get_cost_control_snapshot().to_dict(),
        thresholds={
            "retrieval_hit_target": settings.eval_retrieval_hit_target,
            "faithfulness_target": settings.eval_faithfulness_target,
            "taxonomy_accuracy_target": settings.eval_taxonomy_accuracy_target,
            "rag_min_top_score": settings.rag_min_top_score,
            "rag_min_avg_score": settings.rag_min_avg_score,
        },
        passed=passed,
        notes=notes,
    )

    if persist and session is not None:
        _persist_eval_run(session, report)
        session.commit()

    return report


def _persist_eval_run(session: Session, report: EvalReport) -> None:
    row = EvalRun(
        run_version=report.run_version,
        retrieval_hit_at_k=report.retrieval.details.get("hit_at_k"),
        retrieval_mrr=report.retrieval.details.get("mrr"),
        faithfulness_score=report.faithfulness.value,
        taxonomy_accuracy=report.taxonomy.value,
        passed=report.passed,
        report=report.to_dict(),
    )
    session.add(row)
    logger.info("Persisted EvalRun %s passed=%s", report.run_version, report.passed)


def write_eval_report(report: EvalReport, path: str | None = None) -> Path:
    """Write evaluation report JSON to disk."""
    settings = get_settings()
    output = Path(path or settings.eval_report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    logger.info("Wrote evaluation report to %s", output)
    return output
