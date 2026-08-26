"""Non-conversion reason taxonomy from doc/context.md §8."""

from __future__ import annotations

import re
from dataclasses import dataclass

REASON_CATEGORIES: dict[str, list[str]] = {
    "fit_sizing_uncertainty": [
        r"\bfit\b",
        r"\bsiz(e|ing)\b",
        r"\bwrong size\b",
        r"\btoo (?:small|large|tight|loose)\b",
        r"\bunsure about (?:the )?fit\b",
        r"\bpreferred size is unavailable\b",
    ],
    "price_sensitivity_waiting": [
        r"\bprice (?:is )?too high\b",
        r"\bexpensive\b",
        r"\bwait(?:ing)? for (?:a )?(?:sale|discount|coupon|offer|price drop)\b",
        r"\bprice drop\b",
        r"\bbudget\b",
        r"\bslash(?:ed)? prices\b",
    ],
    "quality_trust_doubt": [
        r"\bquality\b",
        r"\bmaterial\b",
        r"\bfabric\b",
        r"\bdistrust\b",
        r"\bconcerned about quality\b",
        r"\bnot as (?:shown|described)\b",
        r"\bfake\b",
    ],
    "styling_decision_uncertainty": [
        r"\bstyling\b",
        r"\bunsure how to style\b",
        r"\bindecisive\b",
        r"\bchange my mind\b",
        r"\bcan(?:'|no)?t decide\b",
        r"\bwhich (?:one|option)\b",
    ],
    "review_trust": [
        r"\breview(?:s)?\b",
        r"\btoo few reviews\b",
        r"\bconflicting reviews\b",
        r"\bfake reviews\b",
        r"\btrust\b",
    ],
    "timing_occasion": [
        r"\boccasion\b",
        r"\bnot needed yet\b",
        r"\bfuture (?:event|occasion)\b",
        r"\bseasonal\b",
        r"\bnot yet\b",
        r"\bdo not need the item\b",
    ],
    "external_comparison": [
        r"\bcompar",
        r"\bamazon\b",
        r"\bflipkart\b",
        r"\bnykaa\b",
        r"\bajio\b",
        r"\bother (?:app|site|platform|store)\b",
        r"\boutside myntra\b",
        r"\bcheck(?:ed|ing)? online\b",
        r"\bswitch(?:ed|ing)? (?:to|apps?)\b",
    ],
    "passive_bookmarking": [
        r"\bbookmark\b",
        r"\bsave for inspiration\b",
        r"\bdo not revisit\b",
        r"\bpassive\b",
        r"\binspiration\b",
        r"\bjust (?:saving|browsing)\b",
    ],
    "logistics_friction": [
        r"\bdelivery\b",
        r"\breturn policy\b",
        r"\bout of stock\b",
        r"\bunavailable\b",
        r"\bpayment\b",
        r"\bcustomer care\b",
        r"\bdelayed\b",
    ],
    "competitive_platform_preference": [
        r"\bprefer (?:nykaa|ajio|amazon|flipkart|another app)\b",
        r"\bbetter on (?:nykaa|ajio|amazon|flipkart)\b",
        r"\bwishlist on (?:nykaa|ajio) (?:instead|more)\b",
        r"\bswitched to (?:nykaa|ajio)\b",
        r"\bnykaa (?:for|is better)\b",
        r"\bajio (?:for|is better|cheaper)\b",
        r"\bmyntra (?:vs|versus)\b",
    ],
}

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    category: [re.compile(p, re.IGNORECASE) for p in patterns]
    for category, patterns in REASON_CATEGORIES.items()
}

SIGNAL_TO_REASON: dict[str, str] = {
    "fit_size_styling_quality_trust_occasion": "fit_sizing_uncertainty",
    "price_sensitivity_waiting": "price_sensitivity_waiting",
    "external_comparison_seeking": "external_comparison",
    "purchase_hesitation": "styling_decision_uncertainty",
    "delayed_decision": "timing_occasion",
    "wishlist_usage": "passive_bookmarking",
}


@dataclass(frozen=True, slots=True)
class ReasonClassification:
    primary: str | None
    scores: dict[str, int]
    matched: list[str]


def classify_reason(text: str, *, signals: list[str] | None = None) -> ReasonClassification:
    """Classify text into taxonomy reason categories; return primary + all scores."""
    scores: dict[str, int] = {}
    matched: list[str] = []

    for category, patterns in _COMPILED.items():
        count = sum(1 for p in patterns if p.search(text))
        if count:
            scores[category] = count
            matched.append(category)

    if signals:
        for signal in signals:
            mapped = SIGNAL_TO_REASON.get(signal)
            if mapped:
                scores[mapped] = scores.get(mapped, 0) + 1
                if mapped not in matched:
                    matched.append(mapped)

    if not scores:
        return ReasonClassification(primary=None, scores={}, matched=[])

    primary = max(scores, key=lambda k: scores[k])
    return ReasonClassification(primary=primary, scores=scores, matched=matched)
