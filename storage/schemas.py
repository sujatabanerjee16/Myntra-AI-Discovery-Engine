"""Pydantic schemas for storage and retrieval APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from common.models import SourceType


class RetrievalFilters(BaseModel):
    source: SourceType | None = None
    sources: list[str] | None = None
    category: str | None = None
    occasion: str | None = None
    price_band: str | None = None
    segment: str | None = None
    signals: list[str] | None = None
    min_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=3)
    top_k: int = Field(default=8, ge=1, le=50)
    filters: RetrievalFilters | None = None


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    score: float
    source: SourceType
    source_ref: str | None
    category: str | None
    occasion: str | None
    price_band: str | None
    segment: str | None
    matched_signals: list[str]
    quality_score: float | None
    document_created_at: datetime | None


class RetrievalSearchResponse(BaseModel):
    query: str
    top_k: int
    filters: RetrievalFilters | None
    results: list[RetrievedChunk]


class StorageStatsResponse(BaseModel):
    document_count: int
    chunk_count: int
    embedded_chunk_count: int
    by_source: dict[str, int]
    latest_run_version: str | None


class DocumentSummary(BaseModel):
    id: uuid.UUID
    source: SourceType
    source_ref: str | None
    language: str | None
    created_at: datetime | None
    ingested_at: datetime
    run_version: str | None
    chunk_count: int
    text_preview: str


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentSummary]
