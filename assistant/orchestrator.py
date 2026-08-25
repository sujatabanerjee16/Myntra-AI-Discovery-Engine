"""RAG orchestrator: retrieve, rerank, ground, generate, and trace answers."""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from api import backend
from api.json_dashboard import fetch_relevant_aggregates_json
from assistant.context import build_grounded_context, fetch_relevant_aggregates
from assistant.guardrails import (
    assess_evidence,
    build_insufficient_evidence_answer,
    build_limitations,
    build_out_of_scope_answer,
    citations_from_chunks,
    compute_answer_confidence,
    format_trace_citations,
    question_in_scope,
)
from assistant.llm import generate_grounded_answer, select_citations
from assistant.query import understand_query
from assistant.rerank import rerank_chunks
from assistant.schemas import AssistantAskResponse
from common.config import get_settings
from common.models import AnswerTrace
from common.observability import RagTraceMetrics, log_rag_trace, timed_operation
from storage.schemas import RetrievalFilters

logger = logging.getLogger(__name__)


def answer_question(
    session: Session,
    *,
    question: str,
    filters: RetrievalFilters | None = None,
    persist_trace: bool = True,
) -> AssistantAskResponse:
    """Run the full grounded RAG pipeline for a business question."""
    settings = get_settings()
    start = time.perf_counter()
    trace = RagTraceMetrics(question=question)

    parsed = understand_query(question, filters)
    json_mode = backend.use_json_backend()
    if json_mode:
        persist_trace = False

    # Domain scope gate: refuse off-topic questions before retrieval so we never
    # fabricate a grounded-looking answer for something outside the corpus's domain.
    # An explicitly detected platform (Myntra/Nykaa/Ajio) is always in scope.
    if not question_in_scope(parsed.question) and not parsed.platforms:
        trace.insufficient_evidence = True
        answer_text = build_out_of_scope_answer(parsed.question)
        confidence = 0.0
        trace.confidence = confidence
        limitations = (
            "This assistant only answers questions about wishlist behavior, purchase "
            "conversion, and fashion e-commerce (e.g. Myntra, Nykaa, Ajio). The question "
            "appears to be outside that scope, so no grounded answer was generated."
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        trace_id = _persist_trace(
            session,
            question=parsed.question,
            answer=answer_text,
            citations=[],
            confidence=confidence,
            limitations=limitations,
            chunk_ids=[],
            duration_ms=duration_ms,
            insufficient_evidence=True,
            persist=persist_trace,
        )
        log_rag_trace(trace)
        if not json_mode:
            session.commit()
        return AssistantAskResponse(
            trace_id=trace_id,
            question=parsed.question,
            answer=answer_text,
            citations=[],
            confidence=confidence,
            limitations=limitations,
            insufficient_evidence=True,
            retrieved_chunk_count=0,
            reason_categories=parsed.reason_categories,
        )

    with timed_operation(trace, "retrieve", top_k=settings.retrieval_top_k):
        retrieved = backend.search_with_fallback(
            session,
            query_text=parsed.search_query,
            top_k=settings.retrieval_top_k,
            filters=parsed.filters,
        )
    trace.retrieved_count = len(retrieved)

    with timed_operation(trace, "rerank", top_k=settings.rag_rerank_top_k):
        reranked = rerank_chunks(
            parsed.question,
            retrieved,
            top_k=settings.rag_rerank_top_k,
        )
    trace.reranked_count = len(reranked)

    with timed_operation(trace, "aggregates"):
        aggregates = (
            fetch_relevant_aggregates_json(parsed.reason_categories)
            if json_mode
            else fetch_relevant_aggregates(session, parsed.reason_categories)
        )

    context = build_grounded_context(reranked, aggregates)
    assessment = assess_evidence(reranked)

    aggregate_confidences = [
        float(item["confidence"])
        for item in aggregates.ranked_reasons
        if item.get("confidence") is not None
    ]

    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    if not assessment.sufficient:
        trace.insufficient_evidence = True
        answer_text = build_insufficient_evidence_answer(parsed.question, assessment)
        citations = citations_from_chunks(reranked, max_citations=3)
        confidence = compute_answer_confidence(reranked, aggregate_confidences) * 0.5
        trace.confidence = confidence
        limitations = build_limitations(
            reranked,
            run_version=aggregates.run_version,
            reason_categories=parsed.reason_categories,
        )
        trace_id = _persist_trace(
            session,
            question=parsed.question,
            answer=answer_text,
            citations=format_trace_citations(citations),
            confidence=confidence,
            limitations=limitations,
            chunk_ids=[chunk.chunk_id for chunk in reranked],
            duration_ms=duration_ms,
            insufficient_evidence=True,
            persist=persist_trace,
        )
        log_rag_trace(trace)
        if not json_mode:
            session.commit()
        return AssistantAskResponse(
            trace_id=trace_id,
            question=parsed.question,
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            limitations=limitations,
            insufficient_evidence=True,
            retrieved_chunk_count=len(reranked),
            reason_categories=parsed.reason_categories,
        )

    with timed_operation(trace, "generate"):
        generated = generate_grounded_answer(parsed.question, context, reranked, aggregates)

    citations = select_citations(reranked, generated.cited_indices)
    confidence = compute_answer_confidence(reranked, aggregate_confidences)
    trace.confidence = confidence
    limitations = build_limitations(
        reranked,
        run_version=aggregates.run_version,
        reason_categories=parsed.reason_categories,
    )

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    trace_id = _persist_trace(
        session,
        question=parsed.question,
        answer=generated.answer,
        citations=format_trace_citations(citations),
        confidence=confidence,
        limitations=limitations,
        chunk_ids=[chunk.chunk_id for chunk in reranked],
        duration_ms=duration_ms,
        insufficient_evidence=False,
        persist=persist_trace,
    )
    log_rag_trace(trace)
    if not json_mode:
        session.commit()

    return AssistantAskResponse(
        trace_id=trace_id,
        question=parsed.question,
        answer=generated.answer,
        citations=citations,
        confidence=confidence,
        limitations=limitations,
        insufficient_evidence=False,
        retrieved_chunk_count=len(reranked),
        reason_categories=parsed.reason_categories,
    )


def _persist_trace(
    session: Session,
    *,
    question: str,
    answer: str,
    citations: list[str],
    confidence: float,
    limitations: str,
    chunk_ids: list,
    duration_ms: float,
    insufficient_evidence: bool,
    persist: bool,
):
    if not persist:
        return None

    trace = AnswerTrace(
        question=question,
        answer=answer,
        citations=citations,
        confidence=confidence,
        limitations=limitations,
        retrieved_chunk_ids=chunk_ids,
        duration_ms=duration_ms,
        insufficient_evidence=insufficient_evidence,
    )
    session.add(trace)
    session.flush()
    logger.info(
        "Persisted AnswerTrace %s question=%r duration_ms=%.2f insufficient=%s",
        trace.id,
        question[:80],
        duration_ms,
        insufficient_evidence,
    )
    return trace.id
