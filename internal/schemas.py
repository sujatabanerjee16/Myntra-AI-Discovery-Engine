"""Internal data schemas for Phase 8."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InternalEventRecord(BaseModel):
    user_hash: str
    product_id: str
    event_type: str
    category: str | None = None
    segment: str | None = None
    price_band: str | None = None
    event_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversionMetricResponse(BaseModel):
    run_version: str
    window_days: int
    wishlist_users: int
    converted_users: int
    conversion_rate: float
    non_conversion_rate: float
    cohort_start: datetime | None
    cohort_end: datetime | None


class ReasonCorroborationItem(BaseModel):
    reason_category: str
    public_confidence: float | None
    public_evidence_volume: int
    internal_non_conversion_share: float | None
    corroboration_score: float
    status: str
    segment_affinity: list[str] = Field(default_factory=list)


class CorroborationResponse(BaseModel):
    run_version: str
    conversion_rate: float | None
    items: list[ReasonCorroborationItem]


class InsightFeedbackRequest(BaseModel):
    reason_category: str
    insight_id: str | None = None
    verdict: str
    notes: str | None = None
    reviewer: str = "pm"


class InsightFeedbackRecord(BaseModel):
    id: str
    insight_id: str | None
    reason_category: str
    verdict: str
    notes: str | None
    reviewer: str
    adjusted_confidence: float | None
    created_at: datetime


class InsightFeedbackListResponse(BaseModel):
    total: int
    feedback: list[InsightFeedbackRecord]
