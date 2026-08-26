"""Relevance filter for priority corpus signals.

Only feedback related to wishlist usage, purchase hesitation, delayed
decision-making, fit/size/styling/quality/review-trust/occasion uncertainty,
price sensitivity, and external comparison behavior is kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Priority signal groups from doc/context.md §7.2
PRIORITY_SIGNALS: dict[str, list[str]] = {
    "wishlist_usage": [
        r"\bwishlist\b",
        r"\bwish list\b",
        r"\bsaved items?\b",
        r"\bshortlist\b",
        r"\bbookmark(?:ed|ing)?\b",
        r"\bsave(?:d|s)? (?:for later|items?)\b",
    ],
    "purchase_hesitation": [
        r"\bhesitat",
        r"\bunsure\b",
        r"\bnot sure\b",
        r"\bconfus",
        r"\bdoubt",
        r"\buncertain",
        r"\bcan(?:'|no)?t decide\b",
        r"\bsecond guess",
    ],
    "delayed_decision": [
        r"\bdelay",
        r"\bpostpon",
        r"\bput off\b",
        r"\bwait(?:ing)? (?:to buy|before buying|for)\b",
        r"\blater\b",
        r"\bnot yet\b",
        r"\bstill thinking\b",
        r"\btake(?:s)? time\b",
    ],
    # Bare quality/review/trust terms are gated separately — see
    # _QUALITY_TRUST_GATED_PATTERNS — so glowing positive reviews do not match.
    "fit_size_styling_quality_trust_occasion": [
        r"\bfit\b",
        r"\bsiz(e|ing)\b",
        r"\bstyling\b",
        r"\bstyle\b",
        r"\boccasion\b",
        r"\blook(?:s)? (?:good|bad)\b",
        r"\bmaterial\b",
        r"\bfabric\b",
        r"\breturn\b",
    ],
    "price_sensitivity_waiting": [
        r"\bprice\b",
        r"\bexpensive\b",
        r"\bcost(?:ly)?\b",
        r"\bsale\b",
        r"\bdiscount\b",
        r"\bcoupon\b",
        r"\boffer\b",
        r"\bwait(?:ing)? for (?:sale|discount|price drop)\b",
        r"\bprice drop\b",
        r"\bbudget\b",
    ],
    "external_comparison_seeking": [
        r"\bcompar",
        r"\bcheck(?:ed|ing)? (?:on )?(?:amazon|flipkart|other)\b",
        r"\bother (?:app|site|platform|store)\b",
        r"\bsearch(?:ed|ing)? (?:online|outside|elsewhere)\b",
        r"\bask(?:ed|ing)? (?:friend|family|someone)\b",
        r"\bgoogle\b",
        r"\byoutube\b",
        r"\binstagram\b",
        r"\boutside myntra\b",
    ],
}

# Quality/review/trust only count when hesitation/negative cues also appear.
_QUALITY_TRUST_GATED_PATTERNS: list[str] = [
    r"\bquality\b",
    r"\breview(?:s)?\b",
    r"\btrust\b",
]

_HESITATION_CONTEXT = re.compile(
    r"\b(?:"
    r"concern(?:ed|s)?|doubt(?:s|ful)?|worried|worry|hesitat\w*|"
    r"unsure|uncertain|not sure|poor|bad|fake|fraud|low quality|"
    r"might return|want(?:ing)? to return|will return|returning|"
    r"issue(?:s)?|problem(?:s)?|skeptic\w*|distrust|don't trust|do not trust"
    r")\b",
    re.IGNORECASE,
)

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    signal: [re.compile(p, re.IGNORECASE) for p in patterns]
    for signal, patterns in PRIORITY_SIGNALS.items()
}

_QUALITY_TRUST_COMPILED: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in _QUALITY_TRUST_GATED_PATTERNS
]


@dataclass(frozen=True, slots=True)
class RelevanceResult:
    is_relevant: bool
    matched_signals: tuple[str, ...]


def _matches_fit_size_styling_group(text: str) -> bool:
    """Match fit/size/style/occasion freely; gate quality/review/trust on hesitation."""
    base_patterns = _COMPILED["fit_size_styling_quality_trust_occasion"]
    if any(p.search(text) for p in base_patterns):
        return True
    if _HESITATION_CONTEXT.search(text) and any(
        p.search(text) for p in _QUALITY_TRUST_COMPILED
    ):
        return True
    return False


def detect_signals(text: str) -> list[str]:
    """Return priority signal keys matched in *text*."""
    matched: list[str] = []
    for signal, patterns in _COMPILED.items():
        if signal == "fit_size_styling_quality_trust_occasion":
            if _matches_fit_size_styling_group(text):
                matched.append(signal)
            continue
        if any(p.search(text) for p in patterns):
            matched.append(signal)
    return matched


def is_relevant(text: str, *, always_include: bool = False) -> RelevanceResult:
    """Return whether *text* matches at least one priority signal."""
    if always_include:
        signals = detect_signals(text)
        return RelevanceResult(is_relevant=True, matched_signals=tuple(signals))

    signals = detect_signals(text)
    return RelevanceResult(is_relevant=bool(signals), matched_signals=tuple(signals))
