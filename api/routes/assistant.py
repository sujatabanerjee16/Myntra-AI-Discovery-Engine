"""Grounded RAG assistant HTTP routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assistant.orchestrator import answer_question
from assistant.schemas import (
    AnswerTraceListResponse,
    AnswerTraceRecord,
    AssistantAskRequest,
    AssistantAskResponse,
)
from common.db import get_session
from common.models import AnswerTrace
from storage.schemas import RetrievalFilters

router = APIRouter(prefix="/assistant", tags=["assistant"])

KEY_QUESTIONS = [
    "Why do users add fashion products to their wishlist?",
    "What prevents wishlisted products from eventually being purchased?",
    "What uncertainties remain after users have identified a product they like?",
    "What causes users to postpone a purchase?",
    "How do users compare multiple shortlisted products?",
    "What information do users seek outside Myntra/AJIO before purchasing?",
    "What role do fit, size, styling, price, reviews, occasion and social validation play?",
    "When do users use the wishlist as genuine purchase intent versus "
    "simply as a bookmarking mechanism?",
    "How do these behaviors differ across user segments?",
    "What unmet needs emerge consistently across user conversations?",
]


@router.get("/questions")
def list_key_questions() -> dict[str, list[str]]:
    """Return the key business questions from doc/context.md §9."""
    return {"questions": KEY_QUESTIONS}


@router.post("/ask", response_model=AssistantAskResponse)
def ask_assistant(
    body: AssistantAskRequest,
    session: Session = Depends(get_session),
) -> AssistantAskResponse:
    """Answer a business question using retrieved evidence and aggregate context."""
    filters = body.filters.model_copy() if body.filters else RetrievalFilters()
    # body.platforms are Myntra/Nykaa/Ajio, not scrape sources (play_store/youtube).
    # RetrievalFilters.sources is the scrape-source list; do not overwrite it.

    return answer_question(
        session,
        question=body.question,
        filters=filters,
        persist_trace=body.persist_trace,
    )


@router.get("/traces", response_model=AnswerTraceListResponse)
def list_traces(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> AnswerTraceListResponse:
    """List persisted AnswerTrace audit records."""
    total = session.scalar(select(func.count()).select_from(AnswerTrace)) or 0
    rows = session.execute(
        select(AnswerTrace).order_by(AnswerTrace.created_at.desc()).offset(offset).limit(limit)
    ).scalars()

    traces = [
        AnswerTraceRecord(
            id=row.id,
            question=row.question,
            answer=row.answer,
            citations=row.citations or [],
            confidence=row.confidence,
            limitations=row.limitations,
            retrieved_chunk_ids=row.retrieved_chunk_ids or [],
            created_at=row.created_at,
        )
        for row in rows
    ]
    return AnswerTraceListResponse(total=total, traces=traces)


@router.get("/traces/{trace_id}", response_model=AnswerTraceRecord)
def get_trace(
    trace_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> AnswerTraceRecord:
    """Fetch a single AnswerTrace by id."""
    row = session.get(AnswerTrace, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="AnswerTrace not found")

    return AnswerTraceRecord(
        id=row.id,
        question=row.question,
        answer=row.answer,
        citations=row.citations or [],
        confidence=row.confidence,
        limitations=row.limitations,
        retrieved_chunk_ids=row.retrieved_chunk_ids or [],
        created_at=row.created_at,
    )
