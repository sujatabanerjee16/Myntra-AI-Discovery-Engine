"""Load primary user research responses from Myntra / wishlist survey Excel files."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from common.models import SourceType
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord

# Canonical age segments used across enrichment, filters, and dashboards.
AGE_18_24 = "age_18_24"
AGE_25_35 = "age_25_35"

_AGE_COLUMN_HINTS = ("age", "age range", "which age")
_OPEN_TEXT_HINTS = (
    "improve",
    "share",
    "anything else",
    "reason",
    "real reason",
    "describe",
    "own words",
    "why have you not",
)


def _safe_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _author_hash(timestamp: str) -> str:
    return hashlib.sha256(timestamp.encode()).hexdigest()[:32]


def _find_age_column(columns: list[str]) -> str | None:
    for col in columns:
        lowered = col.lower().strip()
        if any(hint in lowered for hint in _AGE_COLUMN_HINTS):
            return col
    return None


def normalize_age_band(raw: object) -> str | None:
    """Map free-text age answers to age_18_24 or age_25_35."""
    text = _safe_str(raw).lower().replace(" ", "")
    if not text:
        return None
    if "18-24" in text or text in {"18", "18to24", "18–24"}:
        return AGE_18_24
    if any(token in text for token in ("25-35", "25-34", "25–35", "25–34", "25to35", "25to34")):
        return AGE_25_35
    # Numeric ages (rare): bucket into the two primary survey bands.
    match = re.fullmatch(r"(\d{1,2})", text)
    if match:
        age = int(match.group(1))
        if 18 <= age <= 24:
            return AGE_18_24
        if 25 <= age <= 39:
            return AGE_25_35
    return None


def age_band_label(segment: str | None) -> str:
    if segment == AGE_18_24:
        return "18-24"
    if segment == AGE_25_35:
        return "25-35"
    return ""


def _row_to_text(row: pd.Series, columns: list[str], *, age_band: str | None) -> str:
    """Build a narrative document from a survey response row."""
    parts: list[str] = []
    label = age_band_label(age_band)
    if label:
        parts.append(f"Q: Age band\nA: {label}")
    for col in columns:
        value = _safe_str(row.get(col))
        if not value:
            continue
        question = col.strip()
        # Age already emitted as a normalized band above.
        if any(hint in question.lower() for hint in _AGE_COLUMN_HINTS):
            continue
        parts.append(f"Q: {question}\nA: {value}")
    return "\n\n".join(parts)


def _workbook_slug(path: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return slug or "research"


def fetch_research_records(excel_path: str | Path) -> list[RawRecord]:
    """Read wishlist research responses and return relevant raw records."""
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Research Excel not found: {path}")

    df = pd.read_excel(path, sheet_name=0)
    if df.empty:
        return []

    columns = [str(c) for c in df.columns]
    age_col = _find_age_column(columns)
    slug = _workbook_slug(path)
    records: list[RawRecord] = []

    for idx, row in df.iterrows():
        timestamp = _safe_str(row.get(columns[0]))
        age_band = normalize_age_band(row.get(age_col)) if age_col else None
        text = _row_to_text(row, columns, age_band=age_band)
        if not text:
            continue

        # Survey is wishlist-specific; include all rows. Still tag matched signals.
        relevance = is_relevant(text, always_include=True)
        source_ref = f"research:{slug}:row:{idx}"

        created_at: datetime | None = None
        if timestamp:
            try:
                created_at = pd.to_datetime(timestamp).to_pydatetime()
            except (ValueError, TypeError):
                created_at = None

        records.append(
            RawRecord(
                source=SourceType.research,
                source_ref=source_ref,
                text=text,
                author_hash=_author_hash(timestamp or f"{slug}:{idx}"),
                language="en",
                created_at=created_at,
                metadata={
                    "sheet": path.name,
                    "row_index": int(idx),
                    "age_band": age_band,
                    "workbook": slug,
                },
                matched_signals=list(relevance.matched_signals),
            )
        )

    return records


def fetch_research_open_text_records(excel_path: str | Path) -> list[RawRecord]:
    """Extract open-ended free-text answers as separate documents."""
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Research Excel not found: {path}")

    df = pd.read_excel(path, sheet_name=0)
    columns = [str(c) for c in df.columns]
    age_col = _find_age_column(columns)
    slug = _workbook_slug(path)
    open_text_cols = [
        c
        for c in df.columns
        if any(k in str(c).lower() for k in _OPEN_TEXT_HINTS)
    ]

    records: list[RawRecord] = []
    for idx, row in df.iterrows():
        age_band = normalize_age_band(row.get(age_col)) if age_col else None
        label = age_band_label(age_band)
        for col in open_text_cols:
            value = _safe_str(row.get(col))
            if len(value) < 10:
                continue
            relevance = is_relevant(value)
            if not relevance.is_relevant:
                continue
            text = value if not label else f"Age band: {label}. {value}"
            records.append(
                RawRecord(
                    source=SourceType.research,
                    source_ref=f"research:{slug}:open:{idx}:{hash(col) & 0xFFFF}",
                    text=text,
                    author_hash=_author_hash(f"{slug}:{idx}:{col}"),
                    language="en",
                    metadata={
                        "column": str(col),
                        "row_index": int(idx),
                        "age_band": age_band,
                        "workbook": slug,
                        "sheet": path.name,
                    },
                    matched_signals=list(relevance.matched_signals),
                )
            )
    return records


def fetch_all_research_records(excel_paths: list[str | Path]) -> list[RawRecord]:
    """Load row + open-text research documents from one or more Excel workbooks."""
    records: list[RawRecord] = []
    for raw_path in excel_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        records.extend(fetch_research_records(path))
        records.extend(fetch_research_open_text_records(path))
    from ingestion.connectors.research_interviews import fetch_interview_docx_records

    records.extend(fetch_interview_docx_records())
    return records
