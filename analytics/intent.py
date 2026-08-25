"""Wishlist intent detection: active shortlist vs passive bookmarking."""

from __future__ import annotations

import re

from common.models import IntentType

_ACTIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bpurchase\b",
        r"\bbuy(?:ing)?\b",
        r"\beventually purchase\b",
        r"\bwaiting for (?:a )?(?:sale|discount|offer)\b",
        r"\bprice drop\b",
        r"\bshortlist\b",
        r"\bactive(?:ly)? (?:consider|shop)",
        r"\bready to buy\b",
    ]
]

_PASSIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bbookmark\b",
        r"\bsave for inspiration\b",
        r"\bdo not revisit\b",
        r"\bpassive\b",
        r"\bjust browsing\b",
        r"\bnot planning to buy\b",
        r"\bno (?:real )?intent\b",
    ]
]

_WISHLIST_PATTERN = re.compile(r"\bwishlist\b|\bwish list\b|\bsaved items?\b", re.IGNORECASE)


def detect_intent(text: str, *, reason_category: str | None = None) -> IntentType:
    """Classify wishlist intent from chunk/document text."""
    active = sum(1 for p in _ACTIVE_PATTERNS if p.search(text))
    passive = sum(1 for p in _PASSIVE_PATTERNS if p.search(text))

    if reason_category == "passive_bookmarking":
        passive += 2
    if _WISHLIST_PATTERN.search(text) and active > 0:
        active += 1

    if passive > active:
        return IntentType.passive_bookmark
    if active > 0:
        return IntentType.active_shortlist
    return (
        IntentType.active_shortlist
        if _WISHLIST_PATTERN.search(text)
        else IntentType.passive_bookmark
    )
