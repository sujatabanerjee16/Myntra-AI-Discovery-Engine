"""Load primary user research responses from the Myntra Wishlist Excel file."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd

from common.models import SourceType
from ingestion.filters.relevance import is_relevant
from ingestion.schemas import RawRecord


def _safe_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _author_hash(timestamp: str) -> str:
    return hashlib.sha256(timestamp.encode()).hexdigest()[:32]


def _row_to_text(row: pd.Series, columns: list[str]) -> str:
    """Build a narrative document from a survey response row."""
    parts: list[str] = []
    for col in columns:
        value = _safe_str(row.get(col))
        if not value:
            continue
        question = col.strip()
        parts.append(f"Q: {question}\nA: {value}")
    return "\n\n".join(parts)


def fetch_research_records(excel_path: str | Path) -> list[RawRecord]:
    """Read wishlist research responses and return relevant raw records."""
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Research Excel not found: {path}")

    df = pd.read_excel(path, sheet_name=0)
    if df.empty:
        return []

    columns = [str(c) for c in df.columns]
    records: list[RawRecord] = []

    for idx, row in df.iterrows():
        timestamp = _safe_str(row.get(columns[0]))
        text = _row_to_text(row, columns)
        if not text:
            continue

        # Survey is wishlist-specific; include all rows. Still tag matched signals.
        relevance = is_relevant(text, always_include=True)
        source_ref = f"research:myntra-wishlist:row:{idx}"

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
                author_hash=_author_hash(timestamp or str(idx)),
                language="en",
                created_at=created_at,
                metadata={"sheet": path.name, "row_index": int(idx)},
                matched_signals=list(relevance.matched_signals),
            )
        )

    return records


def fetch_research_open_text_records(excel_path: str | Path) -> list[RawRecord]:
    """Extract open-ended free-text answers as separate documents."""
    path = Path(excel_path)
    df = pd.read_excel(path, sheet_name=0)
    open_text_cols = [
        c
        for c in df.columns
        if any(k in str(c).lower() for k in ("improve", "share", "anything else", "reason"))
    ]

    records: list[RawRecord] = []
    for idx, row in df.iterrows():
        for col in open_text_cols:
            value = _safe_str(row.get(col))
            if len(value) < 10:
                continue
            relevance = is_relevant(value)
            if not relevance.is_relevant:
                continue
            records.append(
                RawRecord(
                    source=SourceType.research,
                    source_ref=f"research:myntra-wishlist:open:{idx}:{hash(col) & 0xFFFF}",
                    text=value,
                    author_hash=_author_hash(f"{idx}:{col}"),
                    language="en",
                    metadata={"column": str(col), "row_index": int(idx)},
                    matched_signals=list(relevance.matched_signals),
                )
            )
    return records
