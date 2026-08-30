"""Self-reported purchase habits from the two research Excel workbooks."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from common.config import get_settings
from ingestion.connectors.research_excel import _find_age_column, _safe_str, normalize_age_band

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_PURCHASE_HINTS = ("eventually purchase", "purchase items from your wishlist")
_PLAN_HINTS = ("planned to buy soon", "maybe someday")


def _resolve_workbook(raw: str) -> Path | None:
    path = Path(raw)
    if path.is_file():
        return path
    candidate = _PROJECT_ROOT / raw
    return candidate if candidate.is_file() else None


def _find_column(columns: list[str], hints: tuple[str, ...]) -> str | None:
    for col in columns:
        lowered = str(col).lower()
        if any(hint in lowered for hint in hints):
            return col
    return None


def _counts(series: pd.Series) -> list[dict[str, object]]:
    tallies: Counter[str] = Counter()
    for raw in series:
        label = _safe_str(raw)
        if not label:
            continue
        tallies[label] += 1
    return [{"label": label, "count": count} for label, count in tallies.most_common()]


def get_survey_purchase_habits(*, segment: str | None = None) -> dict:
    """Count self-reported buy-habit answers. Not a checkout conversion rate."""
    settings = get_settings()
    workbooks: list[dict] = []
    respondents = 0

    for raw in settings.research_excel_path_list:
        path = _resolve_workbook(raw)
        if path is None:
            continue
        df = pd.read_excel(path, sheet_name=0)
        if df.empty:
            continue
        columns = [str(c) for c in df.columns]
        age_col = _find_age_column(columns)
        if segment and age_col:
            mask = df[age_col].map(normalize_age_band) == segment
            df = df.loc[mask]
        if df.empty:
            continue

        purchase_col = _find_column(columns, _PURCHASE_HINTS)
        plan_col = _find_column(columns, _PLAN_HINTS)
        question = purchase_col or plan_col
        answers = _counts(df[question]) if question else []
        workbooks.append(
            {
                "file": path.name,
                "n": int(len(df)),
                "question": str(question).strip() if question else None,
                "answers": answers,
            }
        )
        respondents += int(len(df))

    return {
        "respondents": respondents,
        "self_reported": True,
        "checkout_rate_available": False,
        "workbooks": workbooks,
    }
