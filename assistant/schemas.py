"""Pydantic schemas for the grounded RAG assistant."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from storage.schemas import RetrievalFilters


class ParsedQuery(BaseModel):
    """Query understanding output: search text plus optional filters and hints."""

    question: str
    search_query: str
    filters: RetrievalFilters | None = None
    platforms: list[str] | None = None
    reason_categories: list[str] = Field(default_factory=list)
    intent_hint: str | None = None


class AggregateContext(BaseModel):
    """Dashboard aggregates injected as grounded context."""

    run_version: str | None
    ranked_reasons: list[dict[str, object]] = Field(default_factory=list)
    theme_clusters: list[dict[str, object]] = Field(default_factory=list)
    competitive: list[dict[str, object]] = Field(default_factory=list)
    competitive_summary: dict[str, object] = Field(default_factory=dict)
    segment_comparisons: list[dict[str, object]] = Field(default_factory=list)


class Citation(BaseModel):
    chunk_id: uuid.UUID
    source: str
    excerpt: str
    score: float


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    filters: RetrievalFilters | None = None
    platforms: list[str] | None = None
    persist_trace: bool = True


class AssistantAskResponse(BaseModel):
    trace_id: uuid.UUID | None = None
    question: str
    answer: str
    citations: list[Citation]
    confidence: float
    limitations: str
    insufficient_evidence: bool = False
    retrieved_chunk_count: int
    reason_categories: list[str] = Field(default_factory=list)


class AnswerTraceRecord(BaseModel):
    id: uuid.UUID
    question: str
    answer: str | None
    citations: list[str]
    confidence: float | None
    limitations: str | None
    retrieved_chunk_ids: list[uuid.UUID]
    created_at: datetime


class AnswerTraceListResponse(BaseModel):
    total: int
    traces: list[AnswerTraceRecord]
