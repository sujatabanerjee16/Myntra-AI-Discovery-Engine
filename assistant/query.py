"""Query understanding: infer filters and reason hints from a user question."""

from __future__ import annotations

import re

from analytics.intent import detect_intent
from analytics.platforms import tag_platforms
from analytics.taxonomy import REASON_CATEGORIES, classify_reason
from assistant.schemas import ParsedQuery
from common.models import SourceType
from storage.schemas import RetrievalFilters

_SOURCE_ALIASES: dict[str, SourceType] = {
    "play store": SourceType.play_store,
    "playstore": SourceType.play_store,
    "app review": SourceType.play_store,
    "reddit": SourceType.reddit,
    "youtube": SourceType.youtube,
    "product review": SourceType.product_review,
    "social": SourceType.social,
    "research": SourceType.research,
    "user research": SourceType.research,
}

_SEGMENT_KEYWORDS: dict[str, str] = {
    "price sensitive": "price_sensitive",
    "budget": "price_sensitive",
    "quality focused": "quality_focused",
    "fit focused": "fit_focused",
    "occasion driven": "occasion_driven",
}

_CATEGORY_KEYWORDS: dict[str, str] = {
    "footwear": "footwear",
    "shoes": "footwear",
    "dress": "dresses",
    "dresses": "dresses",
    "ethnic": "ethnic_wear",
    "western": "western_wear",
    "accessories": "accessories",
}

_OCCASION_KEYWORDS: dict[str, str] = {
    "wedding": "wedding",
    "festive": "festive",
    "office": "office",
    "casual": "casual",
    "party": "party",
}

_PRICE_BAND_KEYWORDS: dict[str, str] = {
    "premium": "premium",
    "mid range": "mid_range",
    "budget": "budget",
    "sale waiting": "sale_waiting",
    "waiting for sale": "sale_waiting",
}


def _find_alias(text: str, aliases: dict[str, str]) -> str | None:
    lowered = text.lower()
    for phrase, value in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if phrase in lowered:
            return value
    return None


def _detect_reason_categories(question: str) -> list[str]:
    classification = classify_reason(question)
    categories = list(classification.matched)
    if classification.primary and classification.primary not in categories:
        categories.insert(0, classification.primary)

    lowered = question.lower()
    for category in REASON_CATEGORIES:
        label = category.replace("_", " ")
        if label in lowered and category not in categories:
            categories.append(category)

    return categories[:5]


def _detect_fashion_platforms(question: str) -> list[str]:
    """Detect Myntra / Nykaa / Ajio / other mentions for competitive Q&A."""
    tagged = tag_platforms(question)
    # Only keep explicit hits — ignore the soft Myntra default for questions
    # that never named a platform (confidence < 0.5 means default-only).
    if tagged.attribution_confidence < 0.5 and tagged.platforms == ["myntra"]:
        lowered = question.lower()
        competitive_cues = ("vs", "versus", "competitor", "nykaa", "ajio", "compare")
        if any(cue in lowered for cue in competitive_cues):
            return ["myntra", "nykaa", "ajio"]
        return []
    return tagged.platforms


def understand_query(
    question: str,
    explicit_filters: RetrievalFilters | None = None,
) -> ParsedQuery:
    """Parse a business question into retrieval filters and taxonomy hints."""
    normalized = re.sub(r"\s+", " ", question.strip())
    intent_type = detect_intent(normalized)
    fashion_platforms = _detect_fashion_platforms(normalized)

    inferred = RetrievalFilters(
        source=_find_alias(normalized, _SOURCE_ALIASES),
        category=_find_alias(normalized, _CATEGORY_KEYWORDS),
        occasion=_find_alias(normalized, _OCCASION_KEYWORDS),
        price_band=_find_alias(normalized, _PRICE_BAND_KEYWORDS),
        segment=_find_alias(normalized, _SEGMENT_KEYWORDS),
    )

    merged = explicit_filters
    if merged is None:
        merged = inferred
    else:
        merged = RetrievalFilters(
            source=merged.source or inferred.source,
            category=merged.category or inferred.category,
            occasion=merged.occasion or inferred.occasion,
            price_band=merged.price_band or inferred.price_band,
            segment=merged.segment or inferred.segment,
            signals=merged.signals or inferred.signals,
            min_quality_score=merged.min_quality_score or inferred.min_quality_score,
        )

    empty = all(
        getattr(merged, field) is None or (field == "signals" and not merged.signals)
        for field in RetrievalFilters.model_fields
    )
    filters = None if empty else merged

    reason_categories = _detect_reason_categories(normalized)
    if fashion_platforms and "competitive_platform_preference" not in reason_categories:
        # Competitive questions should retrieve comparison / preference evidence.
        reason_categories = ["competitive_platform_preference", "external_comparison", *reason_categories][:5]

    search_query = normalized
    if fashion_platforms:
        search_query = f"{normalized} wishlist {' '.join(fashion_platforms)}"

    return ParsedQuery(
        question=normalized,
        search_query=search_query,
        filters=filters,
        platforms=fashion_platforms or None,
        reason_categories=reason_categories,
        intent_hint=intent_type.value,
    )
