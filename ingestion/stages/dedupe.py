"""Near-duplicate detection and removal."""

from __future__ import annotations

import hashlib
import re

from ingestion.schemas import RawRecord

_NORM = re.compile(r"[^a-z0-9\s]+")


def content_fingerprint(text: str) -> str:
    normalized = _NORM.sub("", text.lower())
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def dedupe_records(records: list[RawRecord]) -> list[RawRecord]:
    seen_refs: set[str] = set()
    seen_content: set[str] = set()
    out: list[RawRecord] = []

    for record in records:
        ref_key = f"{record.source.value}:{record.source_ref}"
        if ref_key in seen_refs:
            continue

        fp = content_fingerprint(record.text)
        if fp in seen_content:
            continue

        seen_refs.add(ref_key)
        seen_content.add(fp)
        out.append(record)

    return out
