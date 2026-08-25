"""File-backed PM insight feedback store (JSON fallback when Postgres is down)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common.config import get_settings
from internal.feedback import adjust_confidence
from internal.schemas import InsightFeedbackListResponse, InsightFeedbackRecord

_lock = threading.Lock()


def _feedback_path() -> Path:
    settings = get_settings()
    path = Path(getattr(settings, "feedback_json_path", "data/insight_feedback.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_all() -> list[dict[str, Any]]:
    path = _feedback_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, list):
        return payload
    return list(payload.get("feedback") or [])


def _write_all(rows: list[dict[str, Any]]) -> None:
    path = _feedback_path()
    path.write_text(json.dumps({"feedback": rows}, indent=2, default=str), encoding="utf-8")


def _base_confidence_for_reason(reason_category: str) -> float | None:
    from api.json_store import load_insights_payload

    payload = load_insights_payload()
    for row in payload.get("reasons") or []:
        if row.get("reason_category") == reason_category:
            conf = row.get("confidence")
            return float(conf) if conf is not None else None
    confidences = [
        float(row["confidence"])
        for row in payload.get("insights") or []
        if row.get("reason_category") == reason_category and row.get("confidence") is not None
    ]
    if not confidences:
        return None
    return round(sum(confidences) / len(confidences), 3)


def append_feedback(
    *,
    reason_category: str,
    verdict: str,
    notes: str | None = None,
    reviewer: str = "pm",
    insight_id: str | None = None,
) -> InsightFeedbackRecord:
    base = _base_confidence_for_reason(reason_category)
    adjusted = adjust_confidence(base, verdict)
    record = {
        "id": str(uuid.uuid4()),
        "insight_id": insight_id,
        "reason_category": reason_category,
        "verdict": verdict,
        "notes": notes,
        "reviewer": reviewer or "pm",
        "adjusted_confidence": adjusted,
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _lock:
        rows = _read_all()
        rows.insert(0, record)
        _write_all(rows)
    return InsightFeedbackRecord(
        id=record["id"],
        insight_id=record["insight_id"],
        reason_category=record["reason_category"],
        verdict=record["verdict"],
        notes=record["notes"],
        reviewer=record["reviewer"],
        adjusted_confidence=record["adjusted_confidence"],
        created_at=datetime.fromisoformat(record["created_at"]),
    )


def list_feedback(
    *,
    reason_category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> InsightFeedbackListResponse:
    with _lock:
        rows = _read_all()
    if reason_category:
        rows = [row for row in rows if row.get("reason_category") == reason_category]
    total = len(rows)
    page = rows[offset : offset + limit]
    feedback = [
        InsightFeedbackRecord(
            id=str(row["id"]),
            insight_id=row.get("insight_id"),
            reason_category=row["reason_category"],
            verdict=row["verdict"],
            notes=row.get("notes"),
            reviewer=row.get("reviewer") or "pm",
            adjusted_confidence=row.get("adjusted_confidence"),
            created_at=datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            if row.get("created_at")
            else datetime.now(UTC),
        )
        for row in page
    ]
    return InsightFeedbackListResponse(total=total, feedback=feedback)
