"""Internal data and ground-truth metric HTTP routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from common.config import get_settings
from common.db import get_session
from common.models import (
    ConversionSnapshot,
    FeedbackVerdict,
    Insight,
    InsightFeedback,
    ReasonAggregate,
    ReasonCorroboration,
)
from internal.feedback import adjust_confidence
from internal.offline import get_offline_store, run_offline_internal_pipeline
from internal.pipeline import run_internal_pipeline
from internal.schemas import (
    ConversionMetricResponse,
    CorroborationResponse,
    InsightFeedbackListResponse,
    InsightFeedbackRecord,
    InsightFeedbackRequest,
    ReasonCorroborationItem,
)

router = APIRouter(prefix="/internal", tags=["internal"])


def _conversion_from_offline() -> ConversionMetricResponse | None:
    snapshot = get_offline_store().conversion
    if snapshot is None:
        return None
    return ConversionMetricResponse(
        run_version=snapshot.run_version,
        window_days=snapshot.window_days,
        wishlist_users=snapshot.wishlist_users,
        converted_users=snapshot.converted_users,
        conversion_rate=snapshot.conversion_rate,
        non_conversion_rate=round(1.0 - snapshot.conversion_rate, 4),
        cohort_start=snapshot.cohort_start,
        cohort_end=snapshot.cohort_end,
    )


def _corroboration_from_offline() -> CorroborationResponse | None:
    store = get_offline_store()
    if store.conversion is None:
        return None
    items = [
        ReasonCorroborationItem(
            reason_category=item["reason_category"],
            public_confidence=item.get("public_confidence"),
            public_evidence_volume=int(item.get("public_evidence_volume") or 0),
            internal_non_conversion_share=item.get("internal_non_conversion_share"),
            corroboration_score=float(item.get("corroboration_score") or 0),
            status=str(item.get("status") or "weak"),
            segment_affinity=list(item.get("segment_affinity") or []),
        )
        for item in store.corroboration_items
    ]
    return CorroborationResponse(
        run_version=store.conversion.run_version,
        conversion_rate=store.conversion.conversion_rate,
        items=items,
    )


@router.get("/conversion", response_model=ConversionMetricResponse)
def get_conversion_metric(session: Session = Depends(get_session)) -> ConversionMetricResponse:
    from api import backend

    # Prefer warmed offline snapshot in JSON/demo mode so Render free-tier
    # restarts still serve numbers without waiting on Postgres.
    if backend.use_json_backend():
        offline = _conversion_from_offline()
        if offline is not None:
            return offline

    try:
        row = session.execute(
            select(ConversionSnapshot).order_by(ConversionSnapshot.computed_at.desc()).limit(1)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        row = None

    if row is not None:
        return ConversionMetricResponse(
            run_version=row.run_version,
            window_days=row.window_days,
            wishlist_users=row.wishlist_users,
            converted_users=row.converted_users,
            conversion_rate=row.conversion_rate,
            non_conversion_rate=round(1.0 - row.conversion_rate, 4),
            cohort_start=row.cohort_start,
            cohort_end=row.cohort_end,
        )

    offline = _conversion_from_offline()
    if offline is not None:
        return offline

    return ConversionMetricResponse(
        run_version="unknown",
        window_days=30,
        wishlist_users=0,
        converted_users=0,
        conversion_rate=0.0,
        non_conversion_rate=1.0,
        cohort_start=None,
        cohort_end=None,
    )


@router.get("/corroboration", response_model=CorroborationResponse)
def get_corroboration(session: Session = Depends(get_session)) -> CorroborationResponse:
    try:
        conversion = session.execute(
            select(ConversionSnapshot).order_by(ConversionSnapshot.computed_at.desc()).limit(1)
        ).scalar_one_or_none()
        rows = session.execute(
            select(ReasonCorroboration).order_by(ReasonCorroboration.corroboration_score.desc())
        ).scalars()

        items = [
            ReasonCorroborationItem(
                reason_category=row.reason_category,
                public_confidence=row.public_confidence,
                public_evidence_volume=row.public_evidence_volume,
                internal_non_conversion_share=row.internal_non_conversion_share,
                corroboration_score=row.corroboration_score,
                status=row.status,
                segment_affinity=row.segment_affinity or [],
            )
            for row in rows
        ]
        return CorroborationResponse(
            run_version=conversion.run_version if conversion else "unknown",
            conversion_rate=conversion.conversion_rate if conversion else None,
            items=items,
        )
    except SQLAlchemyError:
        offline = _corroboration_from_offline()
        if offline is not None:
            return offline
        return CorroborationResponse(run_version="unknown", conversion_rate=None, items=[])


@router.post("/compute")
def compute_internal_metrics(session: Session = Depends(get_session)) -> dict:
    """Ingest internal events and compute conversion + corroboration."""
    settings = get_settings()
    try:
        result = run_internal_pipeline(session, events_path=settings.internal_events_path)
        session.commit()
        mode = "database"
    except FileNotFoundError as exc:
        try:
            session.rollback()
        except SQLAlchemyError:
            pass
        raise HTTPException(
            status_code=404,
            detail=f"Internal events seed missing: {exc}",
        ) from exc
    except SQLAlchemyError:
        try:
            session.rollback()
        except SQLAlchemyError:
            pass
        # Postgres unavailable — still compute from seed JSON for local demos.
        try:
            result = run_offline_internal_pipeline(settings.internal_events_path)
            mode = "offline"
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Internal events seed missing: {exc}",
            ) from exc
    except Exception as exc:
        try:
            session.rollback()
        except SQLAlchemyError:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Internal compute failed: {exc}",
        ) from exc

    return {
        "run_version": result.run_version,
        "events_loaded": result.events_loaded,
        "conversion_rate": result.conversion_rate,
        "corroborations": result.corroborations,
        "items": result.items,
        "mode": mode,
    }


@router.post("/feedback", response_model=InsightFeedbackRecord)
def submit_insight_feedback(
    body: InsightFeedbackRequest,
    session: Session = Depends(get_session),
) -> InsightFeedbackRecord:
    """Record PM validation/flag feedback and adjust confidence."""
    from api import backend
    from api import json_feedback as json_fb

    try:
        verdict = FeedbackVerdict(body.verdict)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid verdict") from exc

    if backend.use_json_backend():
        return json_fb.append_feedback(
            reason_category=body.reason_category,
            verdict=verdict.value,
            notes=body.notes,
            reviewer=body.reviewer,
            insight_id=body.insight_id,
        )

    insight_uuid = uuid.UUID(body.insight_id) if body.insight_id else None
    base_confidence = None

    try:
        if insight_uuid:
            insight = session.get(Insight, insight_uuid)
            if insight is None:
                raise HTTPException(status_code=404, detail="Insight not found")
            base_confidence = insight.confidence
        else:
            reason_row = session.execute(
                select(ReasonAggregate)
                .where(ReasonAggregate.reason_category == body.reason_category)
                .order_by(ReasonAggregate.computed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            base_confidence = reason_row.confidence if reason_row else None

        adjusted = adjust_confidence(base_confidence, verdict.value)
        row = InsightFeedback(
            insight_id=insight_uuid,
            reason_category=body.reason_category,
            verdict=verdict,
            notes=body.notes,
            reviewer=body.reviewer,
            adjusted_confidence=adjusted,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    except HTTPException:
        raise
    except SQLAlchemyError:
        try:
            session.rollback()
        except SQLAlchemyError:
            pass
        # JSON fallback when Postgres is unreachable
        return json_fb.append_feedback(
            reason_category=body.reason_category,
            verdict=verdict.value,
            notes=body.notes,
            reviewer=body.reviewer,
            insight_id=body.insight_id,
        )

    return InsightFeedbackRecord(
        id=str(row.id),
        insight_id=str(row.insight_id) if row.insight_id else None,
        reason_category=row.reason_category,
        verdict=row.verdict.value,
        notes=row.notes,
        reviewer=row.reviewer,
        adjusted_confidence=row.adjusted_confidence,
        created_at=row.created_at,
    )


@router.get("/feedback", response_model=InsightFeedbackListResponse)
def list_insight_feedback(
    reason_category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> InsightFeedbackListResponse:
    from api import backend
    from api import json_feedback as json_fb

    if backend.use_json_backend():
        return json_fb.list_feedback(
            reason_category=reason_category,
            limit=limit,
            offset=offset,
        )

    try:
        count_stmt = select(func.count()).select_from(InsightFeedback)
        list_stmt = select(InsightFeedback).order_by(InsightFeedback.created_at.desc())
        if reason_category:
            count_stmt = count_stmt.where(InsightFeedback.reason_category == reason_category)
            list_stmt = list_stmt.where(InsightFeedback.reason_category == reason_category)

        total = session.scalar(count_stmt) or 0
        rows = session.execute(list_stmt.offset(offset).limit(limit)).scalars()

        feedback = [
            InsightFeedbackRecord(
                id=str(row.id),
                insight_id=str(row.insight_id) if row.insight_id else None,
                reason_category=row.reason_category,
                verdict=row.verdict.value,
                notes=row.notes,
                reviewer=row.reviewer,
                adjusted_confidence=row.adjusted_confidence,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return InsightFeedbackListResponse(total=total, feedback=feedback)
    except SQLAlchemyError:
        return json_fb.list_feedback(
            reason_category=reason_category,
            limit=limit,
            offset=offset,
        )
