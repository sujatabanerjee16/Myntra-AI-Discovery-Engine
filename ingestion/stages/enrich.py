"""Attach inferred tags and quality scores to chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ingestion.filters.relevance import detect_signals
from ingestion.stages.chunk import TextChunk

_CATEGORY_PATTERNS: dict[str, list[str]] = {
    "clothing": [
        r"\bcloth",
        r"\bdress\b",
        r"\bshirt\b",
        r"\bkurta\b",
        r"\bkurti\b",
        r"\bjeans\b",
        r"\bsaree\b",
        r"\btop\b",
        r"\bethnic\b",
    ],
    "footwear": [
        r"\bshoe",
        r"\bsneaker",
        r"\bfootwear\b",
        r"\bsandal",
        r"\bheel",
        r"\bloafer",
        r"\bboot",
        r"\bslipper",
        r"\bflip[- ]?flop",
    ],
    "accessories": [r"\baccessor", r"\bbag\b", r"\bwatch\b", r"\bjewell?ery\b", r"\bearing"],
    "beauty": [
        r"\bbeauty\b",
        r"\bmakeup\b",
        r"\bskin ?care\b",
        r"\blipstick\b",
        r"\bkajal\b",
        r"\bfoundation\b",
        r"\bserum\b",
        r"\bmoisturizer\b",
        r"\beyeliner\b",
    ],
}

_OCCASION_PATTERNS: dict[str, list[str]] = {
    "wedding": [r"\bwedding\b", r"\bshaadi\b"],
    "festive": [r"\bfestiv", r"\bdiwali\b", r"\beid\b"],
    "casual": [r"\bcasual\b", r"\bdaily\b"],
    "office": [r"\boffice\b", r"\bwork\b", r"\bformal\b"],
}

_PRICE_PATTERNS: dict[str, list[str]] = {
    "budget": [r"\bbudget\b", r"\bcheap\b", r"\baffordable\b"],
    "mid": [r"\bmid[- ]range\b", r"\bmoderate\b"],
    "premium": [r"\bexpensive\b", r"\bpremium\b", r"\bluxury\b"],
    "sale_waiting": [
        r"\bwait(?:ing)? for (?:a )?(?:sale|discount|offer|price drop)\b",
        r"\bprice drop\b",
    ],
}

_SEGMENT_PATTERNS: dict[str, list[str]] = {
    "age_18_24": [r"\bage\s*band\s*[:\-]?\s*18\s*[-–]\s*24\b", r"\b18\s*[-–]\s*24\b"],
    "age_25_35": [
        r"\bage\s*band\s*[:\-]?\s*25\s*[-–]\s*3[45]\b",
        r"\b25\s*[-–]\s*3[45]\b",
    ],
    "comparison_shopper": [r"\bcompar", r"\bother app\b", r"\bflipkart\b", r"\bamazon\b"],
    "price_sensitive": [r"\bprice\b", r"\bsale\b", r"\bdiscount\b", r"\boffer\b"],
    "fit_uncertain": [r"\bfit\b", r"\bsiz(e|ing)\b", r"\bunsure about fit\b"],
    "quality_concerned": [r"\bquality\b", r"\bmaterial\b", r"\bfabric\b"],
}


def _first_match(text: str, patterns: dict[str, list[str]]) -> str | None:
    for label, regexes in patterns.items():
        if any(re.search(p, text, re.IGNORECASE) for p in regexes):
            return label
    return None


@dataclass(slots=True)
class EnrichedChunk:
    chunk: TextChunk
    category: str | None = None
    occasion: str | None = None
    price_band: str | None = None
    segment: str | None = None
    quality_score: float = 0.5
    signals: list[str] = field(default_factory=list)


def _quality_score(text: str, signals: list[str]) -> float:
    score = 0.35
    score += min(len(text) / 500, 0.25)
    score += min(len(signals) * 0.08, 0.3)
    if len(text.split()) >= 8:
        score += 0.1
    return round(min(score, 1.0), 3)


def enrich_chunk(chunk: TextChunk) -> EnrichedChunk:
    text = chunk.text
    signals = chunk.matched_signals or detect_signals(text)
    # Prefer explicit survey age metadata over inferred behavioral segments.
    age_band = chunk.metadata.get("age_band") if chunk.metadata else None
    segment = age_band if isinstance(age_band, str) and age_band else _first_match(
        text, _SEGMENT_PATTERNS
    )
    return EnrichedChunk(
        chunk=chunk,
        category=_first_match(text, _CATEGORY_PATTERNS),
        occasion=_first_match(text, _OCCASION_PATTERNS),
        price_band=_first_match(text, _PRICE_PATTERNS),
        segment=segment,
        quality_score=_quality_score(text, signals),
        signals=signals,
    )


def enrich_chunks(chunks: list[TextChunk]) -> list[EnrichedChunk]:
    return [enrich_chunk(c) for c in chunks]
