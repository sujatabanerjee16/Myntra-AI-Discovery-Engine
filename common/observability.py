"""Structured observability helpers for pipeline and RAG tracing."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OperationMetric:
    """Single timed operation with optional metadata."""

    name: str
    duration_ms: float
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RagTraceMetrics:
    """Metrics captured during one RAG answer pipeline run."""

    question: str
    operations: list[OperationMetric] = field(default_factory=list)
    retrieved_count: int = 0
    reranked_count: int = 0
    insufficient_evidence: bool = False
    confidence: float | None = None

    @property
    def total_duration_ms(self) -> float:
        return round(sum(op.duration_ms for op in self.operations), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question[:120],
            "total_duration_ms": self.total_duration_ms,
            "retrieved_count": self.retrieved_count,
            "reranked_count": self.reranked_count,
            "insufficient_evidence": self.insufficient_evidence,
            "confidence": self.confidence,
            "operations": [
                {
                    "name": op.name,
                    "duration_ms": op.duration_ms,
                    "success": op.success,
                    **op.metadata,
                }
                for op in self.operations
            ],
        }


@contextmanager
def timed_operation(
    trace: RagTraceMetrics,
    name: str,
    **metadata: Any,
) -> Iterator[None]:
    """Record duration and success for a named RAG sub-step."""
    start = time.perf_counter()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        trace.operations.append(
            OperationMetric(
                name=name,
                duration_ms=duration_ms,
                success=success,
                metadata=metadata,
            )
        )
        logger.debug(
            "RAG step %s completed in %.2fms success=%s metadata=%s",
            name,
            duration_ms,
            success,
            metadata or {},
        )


def log_rag_trace(trace: RagTraceMetrics) -> None:
    """Emit a structured info log for audit and quality review."""
    logger.info(
        "RAG trace question=%r duration_ms=%.2f retrieved=%s reranked=%s "
        "insufficient=%s confidence=%s",
        trace.question[:80],
        trace.total_duration_ms,
        trace.retrieved_count,
        trace.reranked_count,
        trace.insufficient_evidence,
        trace.confidence,
    )


def log_pipeline_run(
    *,
    run_type: str,
    run_version: str,
    duration_ms: float,
    success: bool,
    stats: dict[str, Any],
    error: str | None = None,
) -> None:
    """Emit structured pipeline run metrics."""
    level = logging.INFO if success else logging.ERROR
    logger.log(
        level,
        "Pipeline run type=%s version=%s duration_ms=%.2f success=%s stats=%s error=%s",
        run_type,
        run_version,
        duration_ms,
        success,
        stats,
        error,
    )


def persist_pipeline_run(
    session,
    *,
    run_type: str,
    run_version: str,
    duration_ms: float,
    success: bool,
    stats: dict[str, Any],
    error: str | None = None,
) -> None:
    """Persist pipeline run metrics for observability dashboards."""
    from common.models import PipelineRun

    row = PipelineRun(
        run_type=run_type,
        run_version=run_version,
        duration_ms=round(duration_ms, 2),
        success=success,
        stats=stats,
        error_message=error,
    )
    session.add(row)
