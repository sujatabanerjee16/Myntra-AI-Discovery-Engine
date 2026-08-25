"""Wishlist motive classification (competitive lens).

Answers *why users save/wishlist on a platform* — orthogonal to non-conversion
reason taxonomy. Used for Myntra vs Nykaa vs Ajio comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WISHLIST_MOTIVES: dict[str, list[str]] = {
    "assortment_discovery": [
        r"\bassortment\b",
        r"\bwide (?:range|selection|catalog|catalogue)\b",
        r"\bdiscover(?:y|ing)?\b",
        r"\bbrows(?:e|ing)\b",
        r"\blots? of options\b",
        r"\bvariety\b",
        r"\bcollection\b",
    ],
    "price_sale_waiting": [
        r"\bsale\b",
        r"\bdiscount\b",
        r"\bprice drop\b",
        r"\bcoupon\b",
        r"\boffer\b",
        r"\bcheaper\b",
        r"\bwait(?:ing)? for (?:a )?(?:sale|discount)\b",
        r"\beors\b",
        r"\bend of reason\b",
    ],
    "brand_exclusive": [
        r"\bexclusive\b",
        r"\bbrand(?:s)?\b",
        r"\blimited (?:drop|edition)\b",
        r"\bonly on\b",
        r"\bofficial store\b",
    ],
    "category_strength": [
        r"\bbeauty\b",
        r"\bskincare\b",
        r"\bmakeup\b",
        r"\bapparel\b",
        r"\bfashion\b",
        r"\bfootwear\b",
        r"\bethnic\b",
        r"\bprivate label\b",
        r"\bbetter for (?:beauty|clothes|fashion|makeup)\b",
    ],
    "trust_quality": [
        r"\bauthentic\b",
        r"\bauthenticity\b",
        r"\bgenuine\b",
        r"\bquality\b",
        r"\btrust\b",
        r"\breturn(?:s| policy)?\b",
    ],
    "ux_convenience": [
        r"\beas(?:y|ier) to (?:browse|save|wishlist|use)\b",
        r"\bapp (?:is )?(?:better|faster|smoother)\b",
        r"\bconvenient\b",
        r"\bui\b",
        r"\bux\b",
        r"\bwishlist (?:feature|button)\b",
    ],
    "social_inspiration": [
        r"\binspiration\b",
        r"\bmoodboard\b",
        r"\btrend\b",
        r"\binfluencer\b",
        r"\bhaul\b",
        r"\bjust saving\b",
        r"\bbookmark\b",
    ],
}

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    motive: [re.compile(p, re.IGNORECASE) for p in patterns]
    for motive, patterns in WISHLIST_MOTIVES.items()
}

# Soft priors: if a platform is mentioned with weak motive signal, bias default motive.
PLATFORM_MOTIVE_PRIOR: dict[str, str] = {
    "myntra": "assortment_discovery",
    "nykaa": "category_strength",
    "ajio": "price_sale_waiting",
    "other": "price_sale_waiting",
}


@dataclass(frozen=True, slots=True)
class MotiveClassification:
    primary: str
    motives: list[str]
    scores: dict[str, int]


def classify_wishlist_motives(
    text: str,
    *,
    platforms: list[str] | None = None,
) -> MotiveClassification:
    """Classify why a user wishlists / saves — used for competitive comparison."""
    scores: dict[str, int] = {}
    for motive, patterns in _COMPILED.items():
        count = sum(1 for p in patterns if p.search(text))
        if count:
            scores[motive] = count

    if not scores:
        primary_platform = (platforms or ["myntra"])[0]
        primary = PLATFORM_MOTIVE_PRIOR.get(primary_platform, "assortment_discovery")
        return MotiveClassification(primary=primary, motives=[primary], scores={})

    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], k))
    return MotiveClassification(primary=ranked[0], motives=ranked, scores=scores)
