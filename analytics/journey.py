"""Map feedback to stages in the wishlist-to-purchase journey."""

from __future__ import annotations

import re

from common.models import JourneyStage

_STAGE_PATTERNS: dict[JourneyStage, list[str]] = {
    JourneyStage.discovery: [
        r"\bwishlist\b",
        r"\bsave(?:d|s)? items?\b",
        r"\bshortlist\b",
        r"\bbookmark\b",
    ],
    JourneyStage.consideration: [
        r"\bunsure about (?:fit|size|style)\b",
        r"\bcompar",
        r"\bwhich (?:one|option)\b",
        r"\bneed(?:s)? (?:more )?information\b",
    ],
    JourneyStage.hesitation: [
        r"\bhesitat",
        r"\bdoubt\b",
        r"\bconcerned about\b",
        r"\bquality\b",
        r"\btrust\b",
        r"\bprice (?:is )?too high\b",
    ],
    JourneyStage.postponement: [
        r"\bwait(?:ing)? for (?:a )?(?:sale|discount|offer|price drop)\b",
        r"\bpostpon",
        r"\blater\b",
        r"\bnot yet\b",
        r"\bnot need(?:ed)? (?:the item|it)\b",
    ],
    JourneyStage.external_comparison: [
        r"\bamazon\b",
        r"\bflipkart\b",
        r"\bother app\b",
        r"\boutside myntra\b",
        r"\bcheck(?:ed|ing)? (?:online|elsewhere)\b",
    ],
    JourneyStage.purchase: [
        r"\bpurchas(?:e|ed|ing)\b",
        r"\bbought\b",
        r"\bordered\b",
        r"\bcheckout\b",
    ],
}

_COMPILED = {
    stage: [re.compile(p, re.IGNORECASE) for p in patterns]
    for stage, patterns in _STAGE_PATTERNS.items()
}

_REASON_DEFAULT_STAGE: dict[str, JourneyStage] = {
    "fit_sizing_uncertainty": JourneyStage.consideration,
    "price_sensitivity_waiting": JourneyStage.postponement,
    "quality_trust_doubt": JourneyStage.hesitation,
    "styling_decision_uncertainty": JourneyStage.consideration,
    "review_trust": JourneyStage.hesitation,
    "timing_occasion": JourneyStage.postponement,
    "external_comparison": JourneyStage.external_comparison,
    "passive_bookmarking": JourneyStage.discovery,
    "logistics_friction": JourneyStage.hesitation,
}


def map_journey_stage(text: str, *, reason_category: str) -> JourneyStage:
    """Infer the most likely journey stage for a chunk."""
    scores: dict[JourneyStage, int] = {}
    for stage, patterns in _COMPILED.items():
        count = sum(1 for p in patterns if p.search(text))
        if count:
            scores[stage] = count

    if scores:
        return max(scores, key=lambda s: (scores[s], s != JourneyStage.discovery))
    return _REASON_DEFAULT_STAGE.get(reason_category, JourneyStage.hesitation)
