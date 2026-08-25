"""Theme clustering for emerging patterns and unmet needs."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "is",
    "it",
    "my",
    "i",
    "q",
}


@dataclass(slots=True)
class AnalyzedChunk:
    chunk_id: UUID | str
    text: str
    source: str
    reason_category: str
    signals: list[str]
    segment: str | None = None
    category: str | None = None
    quality_score: float = 0.5
    platforms: list[str] | None = None
    wishlist_motive: str | None = None
    platform_attribution_confidence: float = 0.5
    comparison_scope: str | None = None


@dataclass(frozen=True, slots=True)
class ThemeClusterResult:
    cluster_key: str
    label: str
    reason_category: str
    chunk_ids: list[str]
    evidence_volume: int
    sources: list[str]


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _signal_overlap(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _cluster_label(chunks: list[AnalyzedChunk]) -> str:
    words: Counter[str] = Counter()
    for chunk in chunks:
        words.update(_tokenize(chunk.text))
    top = [w for w, _ in words.most_common(4)]
    if not top:
        return chunks[0].reason_category.replace("_", " ")
    return " / ".join(top)


def cluster_themes(
    analyzed: list[AnalyzedChunk],
    *,
    min_cluster_size: int = 2,
    signal_threshold: float = 0.34,
) -> list[ThemeClusterResult]:
    """Group analyzed chunks into theme clusters by reason + signal similarity."""
    by_reason: dict[str, list[AnalyzedChunk]] = {}
    for item in analyzed:
        by_reason.setdefault(item.reason_category, []).append(item)

    clusters: list[ThemeClusterResult] = []
    cluster_idx = 0

    for reason, items in sorted(by_reason.items()):
        assigned: set[str] = set()

        for i, seed in enumerate(items):
            seed_id = str(seed.chunk_id)
            if seed_id in assigned:
                continue

            group = [seed]
            assigned.add(seed_id)

            for other in items[i + 1 :]:
                other_id = str(other.chunk_id)
                if other_id in assigned:
                    continue
                overlap = _signal_overlap(seed.signals, other.signals)
                token_overlap = len(_tokenize(seed.text) & _tokenize(other.text)) / max(
                    len(_tokenize(seed.text) | _tokenize(other.text)), 1
                )
                if overlap >= signal_threshold or token_overlap >= 0.2:
                    group.append(other)
                    assigned.add(other_id)

            if len(group) < min_cluster_size:
                continue

            cluster_idx += 1
            chunk_ids = [str(c.chunk_id) for c in group]
            sources = sorted({c.source for c in group})
            clusters.append(
                ThemeClusterResult(
                    cluster_key=f"theme-{cluster_idx:03d}",
                    label=_cluster_label(group),
                    reason_category=reason,
                    chunk_ids=chunk_ids,
                    evidence_volume=len(group),
                    sources=sources,
                )
            )

    return clusters
