"""Pydantic schemas for semantic analytics outputs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from common.models import IntentType, JourneyStage


class InsightRecord(BaseModel):
    id: uuid.UUID
    reason_category: str
    intent_type: IntentType | None
    journey_stage: JourneyStage | None
    segment: str | None
    category: str | None
    evidence_volume: int
    confidence: float | None
    sources: list[str]
    evidence_chunk_ids: list[uuid.UUID]
    run_version: str | None
    created_at: datetime | None = None


class ReasonRankItem(BaseModel):
    reason_category: str
    evidence_volume: int
    confidence: float | None
    sources: list[str]
    active_shortlist_count: int = 0
    passive_bookmark_count: int = 0


class ThemeClusterItem(BaseModel):
    cluster_key: str
    label: str
    reason_category: str | None
    evidence_volume: int
    confidence: float | None
    sources: list[str]
    chunk_ids: list[uuid.UUID]


class AnalyticsRunResult(BaseModel):
    run_version: str
    insights_created: int
    reason_aggregates: int
    theme_clusters: int
    chunks_analyzed: int


class AnalyticsRunRequest(BaseModel):
    run_version: str | None = None
    replace_existing: bool = True


class InsightListResponse(BaseModel):
    total: int
    insights: list[InsightRecord]


class ReasonRankResponse(BaseModel):
    run_version: str | None
    reasons: list[ReasonRankItem]
    scope_note: str | None = None


class ThemeClusterResponse(BaseModel):
    run_version: str | None
    clusters: list[ThemeClusterItem]


class DashboardFiltersResponse(BaseModel):
    run_version: str | None
    segments: list[str]
    categories: list[str]
    occasions: list[str]
    price_bands: list[str]
    reason_categories: list[str]



class CorpusSourceCount(BaseModel):
    source: str
    documents: int
    chunks: int = 0


class CorpusWorkbookCount(BaseModel):
    workbook: str
    respondents: int


class CorpusScrapeStats(BaseModel):
    documents: int
    chunks: int
    by_source: list[CorpusSourceCount] = []
    survey_documents: int = 0
    scraped_documents: int = 0
    survey_respondents: int = 0
    survey_open_text: int = 0
    survey_interviews: int = 0
    survey_by_workbook: list[CorpusWorkbookCount] = []


class HeatmapCell(BaseModel):
    row: str
    column: str
    value: int
    confidence: float | None = None


class HeatmapResponse(BaseModel):
    run_version: str | None
    row_key: str
    column_key: str
    rows: list[str]
    columns: list[str]
    cells: list[HeatmapCell]


class IntentBreakdownItem(BaseModel):
    reason_category: str
    active_shortlist_count: int
    passive_bookmark_count: int
    evidence_volume: int
    confidence: float | None


class IntentBreakdownResponse(BaseModel):
    run_version: str | None
    total_active: int
    total_passive: int
    by_reason: list[IntentBreakdownItem]


class JourneyTrendItem(BaseModel):
    journey_stage: str
    evidence_volume: int
    confidence: float | None


class TrendsResponse(BaseModel):
    run_version: str | None
    journey_stages: list[JourneyTrendItem]
    emerging_themes: list[ThemeClusterItem]


class EvidenceExcerpt(BaseModel):
    chunk_id: uuid.UUID
    text: str
    source: str
    source_ref: str | None
    segment: str | None
    category: str | None
    confidence: float | None
    quality_score: float | None


class EvidenceSummaryResponse(BaseModel):
    run_version: str | None
    reason_category: str
    evidence_volume: int
    confidence: float | None
    sources: list[str]
    excerpts: list[EvidenceExcerpt]


class CompetitiveMetricItem(BaseModel):
    platform: str
    metric_type: str
    label: str
    count: int
    share: float | None = None
    evidence_volume: int
    confidence: float | None = None
    shared_vs_unique: str | None = None
    sources: list[str] = []


class CompetitiveTopItem(BaseModel):
    label: str
    count: int
    share: float | None = None
    confidence: float | None = None


class CompetitiveAnalysisResponse(BaseModel):
    run_version: str | None
    platforms: list[str]
    motives: list[CompetitiveMetricItem]
    barriers: list[CompetitiveMetricItem]
    shared_motives: list[str]
    unique_motives_by_platform: dict[str, list[str]]
    top_motive_by_platform: dict[str, CompetitiveTopItem]
    top_barrier_by_platform: dict[str, CompetitiveTopItem]
    why_not_purchase: list[str]
    limitations: str
