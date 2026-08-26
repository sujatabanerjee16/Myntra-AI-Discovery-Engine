"""Fashion-platform tagging for competitive wishlist analysis.

Detects mentions of Myntra, Nykaa, Ajio, and other marketplaces so the engine
can compare *why* users wishlist / hesitate across platforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical platform ids used across analytics, API, and UI.
PLATFORMS = ("myntra", "nykaa", "ajio", "other")

PLATFORM_ALIASES: dict[str, tuple[str, ...]] = {
    "myntra": (r"\bmyntra\b", r"\bmyntra\.com\b"),
    "nykaa": (r"\bnykaa\b", r"\bnykaa fashion\b", r"\bnykaafashion\b"),
    "ajio": (r"\bajio\b", r"\bajio\.com\b"),
    "other": (
        r"\bamazon\b",
        r"\bflipkart\b",
        r"\bmeesho\b",
        r"\btata cliq\b",
        r"\btatacliq\b",
        r"\bsheen\b",
        r"\bzara\b",
        r"\bh&m\b",
        r"\bother (?:app|site|platform|store)s?\b",
    ),
}

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    platform: [re.compile(p, re.IGNORECASE) for p in patterns]
    for platform, patterns in PLATFORM_ALIASES.items()
}


@dataclass(frozen=True, slots=True)
class PlatformTagResult:
    platforms: list[str]
    attribution_confidence: float
    primary: str | None


def tag_platforms(text: str) -> PlatformTagResult:
    """Return normalized platform tags found in text with attribution confidence."""
    hits: dict[str, int] = {}
    for platform, patterns in _COMPILED.items():
        count = sum(1 for p in patterns if p.search(text))
        if count:
            hits[platform] = count

    if not hits:
        # Default attribution: fashion wishlist talk without an explicit brand
        # is treated as Myntra-scoped directional evidence (corpus is Myntra-led).
        return PlatformTagResult(
            platforms=["myntra"], attribution_confidence=0.35, primary="myntra"
        )

    platforms = sorted(
        hits.keys(), key=lambda p: (-hits[p], PLATFORMS.index(p) if p in PLATFORMS else 99)
    )
    total = sum(hits.values())
    # Higher when multiple explicit mentions or multi-platform comparison.
    confidence = min(0.95, 0.55 + 0.12 * total + (0.1 if len(platforms) > 1 else 0.0))
    return PlatformTagResult(
        platforms=platforms, attribution_confidence=round(confidence, 3), primary=platforms[0]
    )


def comparison_scope(platforms: list[str]) -> str:
    """Classify whether evidence is Myntra-only, competitor-only, shared, or multi."""
    named = {p for p in platforms if p in {"myntra", "nykaa", "ajio", "other"}}
    if not named:
        return "myntra_only"
    has_myntra = "myntra" in named
    competitors = named - {"myntra"}
    if has_myntra and competitors:
        return "multi_platform"
    if has_myntra:
        return "myntra_only"
    return "competitor_only"
