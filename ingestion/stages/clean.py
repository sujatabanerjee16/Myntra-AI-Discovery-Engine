"""Text cleaning and normalization."""

from __future__ import annotations

import re
import unicodedata

from ingestion.schemas import RawRecord

_MULTI_SPACE = re.compile(r"\s+")
_HTML = re.compile(r"<[^>]+>")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _HTML.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def clean_record(record: RawRecord) -> RawRecord | None:
    cleaned = normalize_text(record.text)
    if len(cleaned) < 20:
        return None
    record.text = cleaned
    return record


def clean_records(records: list[RawRecord]) -> list[RawRecord]:
    out: list[RawRecord] = []
    for record in records:
        cleaned = clean_record(record)
        if cleaned is not None:
            out.append(cleaned)
    return out
