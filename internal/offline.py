"""Offline internal metrics when PostgreSQL is unavailable."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from common.config import get_settings
from internal.connectors.events import load_internal_events
from internal.conversion import compute_wishlist_conversion, segment_non_conversion_rates
from internal.corroboration import compute_corroboration
from internal.pipeline import InternalPipelineResult

# Reasonable public-evidence stand-ins used only for offline corroboration demos.
_OFFLINE_REASONS = [
    {"reason_category": "price_sensitivity_waiting", "evidence_volume": 42, "confidence": 0.82},
    {"reason_category": "fit_sizing_uncertainty", "evidence_volume": 28, "confidence": 0.74},
    {"reason_category": "quality_trust_doubt", "evidence_volume": 18, "confidence": 0.61},
    {"reason_category": "styling_decision_uncertainty", "evidence_volume": 12, "confidence": 0.55},
    {"reason_category": "availability_stock", "evidence_volume": 9, "confidence": 0.48},
    {"reason_category": "logistics_friction", "evidence_volume": 7, "confidence": 0.4},
    {"reason_category": "other_unspecified", "evidence_volume": 4, "confidence": 0.3},
]


@dataclass
class OfflineConversionSnapshot:
    run_version: str
    window_days: int
    wishlist_users: int
    converted_users: int
    conversion_rate: float
    cohort_start: datetime | None
    cohort_end: datetime | None


@dataclass
class OfflineStore:
    conversion: OfflineConversionSnapshot | None = None
    corroboration_items: list[dict] = field(default_factory=list)
    pipeline: InternalPipelineResult | None = None


_STORE = OfflineStore()
_LOCK = Lock()


def get_offline_store() -> OfflineStore:
    return _STORE


def run_offline_internal_pipeline(events_path: str | None = None) -> InternalPipelineResult:
    """Compute conversion + corroboration from seed JSON without a database."""
    settings = get_settings()
    path = events_path or settings.internal_events_path
    run_version = datetime.now(UTC).strftime("offline-%Y%m%dT%H%M%SZ")

    events = load_internal_events(path)
    conversion = compute_wishlist_conversion(
        events,
        window_days=settings.conversion_window_days,
    )
    segment_rates = segment_non_conversion_rates(
        events,
        window_days=settings.conversion_window_days,
    )
    corroboration_rows = compute_corroboration(_OFFLINE_REASONS, segment_rates)

    result = InternalPipelineResult(
        run_version=run_version,
        events_loaded=len(events),
        conversion_rate=conversion.conversion_rate,
        corroborations=len(corroboration_rows),
        items=[
            {
                "reason_category": row.reason_category,
                "corroboration_score": row.corroboration_score,
                "status": row.status,
            }
            for row in corroboration_rows
        ],
    )

    snapshot = OfflineConversionSnapshot(
        run_version=run_version,
        window_days=conversion.window_days,
        wishlist_users=conversion.wishlist_users,
        converted_users=conversion.converted_users,
        conversion_rate=conversion.conversion_rate,
        cohort_start=conversion.cohort_start,
        cohort_end=conversion.cohort_end,
    )
    items = [
        {
            "reason_category": row.reason_category,
            "public_confidence": row.public_confidence,
            "public_evidence_volume": row.public_evidence_volume,
            "internal_non_conversion_share": row.internal_non_conversion_share,
            "corroboration_score": row.corroboration_score,
            "status": row.status,
            "segment_affinity": row.segment_affinity,
        }
        for row in corroboration_rows
    ]

    with _LOCK:
        _STORE.conversion = snapshot
        _STORE.corroboration_items = items
        _STORE.pipeline = result

    return result
