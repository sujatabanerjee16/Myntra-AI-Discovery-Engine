"""Evaluation schemas for Phase 6 quality measurement."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrievalEvalCase(BaseModel):
    query: str
    expected_reason_categories: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)


class TaxonomyEvalCase(BaseModel):
    text: str
    expected_category: str
    signals: list[str] = Field(default_factory=list)


class FaithfulnessEvalCase(BaseModel):
    question: str
    answer: str
    evidence_texts: list[str]
    should_refuse: bool = False


class MetricResult(BaseModel):
    name: str
    value: float
    target: float
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class EvalReport(BaseModel):
    run_version: str
    created_at: datetime
    retrieval: MetricResult
    faithfulness: MetricResult
    taxonomy: MetricResult
    cost_controls: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    passed: bool
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["retrieval"] = self.retrieval.model_dump()
        payload["faithfulness"] = self.faithfulness.model_dump()
        payload["taxonomy"] = self.taxonomy.model_dump()
        return payload
