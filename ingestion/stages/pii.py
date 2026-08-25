"""PII scrubbing for public/research feedback."""

from __future__ import annotations

import hashlib
import re

from ingestion.schemas import RawRecord

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{2,4}\)|\d{2,4})[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
)
_HANDLE = re.compile(r"@[A-Za-z0-9_]{2,30}")
_URL = re.compile(r"https?://\S+|www\.\S+")


def scrub_text(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    text = _HANDLE.sub("[handle]", text)
    text = _URL.sub("[url]", text)
    return text


def scrub_record(record: RawRecord) -> RawRecord:
    record.text = scrub_text(record.text)
    if record.author_hash:
        record.author_hash = hashlib.sha256(record.author_hash.encode()).hexdigest()[:32]
    return record


def scrub_records(records: list[RawRecord]) -> list[RawRecord]:
    return [scrub_record(r) for r in records]
