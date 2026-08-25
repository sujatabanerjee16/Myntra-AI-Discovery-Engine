"""Competitive aggregation: motive × platform and barrier × platform."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from analytics.confidence import compute_confidence
from analytics.platforms import PLATFORMS, comparison_scope


def build_competitive_aggregates(
    analyzed_rows: list[dict[str, Any]],
    *,
    run_version: str,
) -> list[dict[str, Any]]:
    """Build CompetitiveAggregate payloads from platform-tagged analyzed chunks.

    Each row should include:
      platforms, wishlist_motive, reason_category, source, quality_score,
      platform_attribution_confidence
    """
    motive_buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "sources": set(),
            "qualities": [],
            "attrib": [],
            "scopes": set(),
        }
    )
    barrier_buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "sources": set(),
            "qualities": [],
            "attrib": [],
            "scopes": set(),
        }
    )

    for row in analyzed_rows:
        platforms = row.get("platforms") or ["myntra"]
        motive = row.get("wishlist_motive") or "assortment_discovery"
        reason = row.get("reason_category") or "styling_decision_uncertainty"
        source = row.get("source") or "research"
        quality = float(row.get("quality_score") or 0.5)
        attrib = float(row.get("platform_attribution_confidence") or 0.5)
        scope = comparison_scope(platforms)

        for platform in platforms:
            if platform not in PLATFORMS:
                platform = "other"
            mb = motive_buckets[(platform, motive)]
            mb["count"] += 1
            mb["sources"].add(source)
            mb["qualities"].append(quality)
            mb["attrib"].append(attrib)
            mb["scopes"].add(scope)

            bb = barrier_buckets[(platform, reason)]
            bb["count"] += 1
            bb["sources"].add(source)
            bb["qualities"].append(quality)
            bb["attrib"].append(attrib)
            bb["scopes"].add(scope)

    # Totals per platform for share calculation.
    motive_totals: dict[str, int] = defaultdict(int)
    barrier_totals: dict[str, int] = defaultdict(int)
    for (platform, _), bucket in motive_buckets.items():
        motive_totals[platform] += bucket["count"]
    for (platform, _), bucket in barrier_buckets.items():
        barrier_totals[platform] += bucket["count"]

    # Shared vs unique: motives/barriers that appear on ≥2 fashion platforms.
    motive_platforms: dict[str, set[str]] = defaultdict(set)
    barrier_platforms: dict[str, set[str]] = defaultdict(set)
    for (platform, label), bucket in motive_buckets.items():
        if bucket["count"] > 0:
            motive_platforms[label].add(platform)
    for (platform, label), bucket in barrier_buckets.items():
        if bucket["count"] > 0:
            barrier_platforms[label].add(platform)

    payloads: list[dict[str, Any]] = []

    def _emit(metric_type: str, buckets: dict, totals: dict, label_platforms: dict) -> None:
        for (platform, label), bucket in buckets.items():
            count = bucket["count"]
            total = max(totals.get(platform, 0), 1)
            sources = sorted(bucket["sources"])
            avg_quality = sum(bucket["qualities"]) / len(bucket["qualities"])
            avg_attrib = sum(bucket["attrib"]) / len(bucket["attrib"])
            confidence = compute_confidence(
                evidence_volume=count,
                sources=set(sources),
                avg_quality=(avg_quality + avg_attrib) / 2,
            )
            shared = "shared" if len(label_platforms.get(label, set())) >= 2 else "unique_to_platform"
            payloads.append(
                {
                    "platform": platform,
                    "metric_type": metric_type,
                    "label": label,
                    "count": count,
                    "share": round(count / total, 4),
                    "evidence_volume": count,
                    "confidence": confidence,
                    "shared_vs_unique": shared,
                    "sources": sources,
                    "run_version": run_version,
                }
            )

    _emit("motive", motive_buckets, motive_totals, motive_platforms)
    _emit("barrier", barrier_buckets, barrier_totals, barrier_platforms)

    payloads.sort(key=lambda r: (r["metric_type"], r["platform"], -r["count"]))
    return payloads


def build_why_not_purchase_narrative(summary: dict[str, Any] | None = None) -> list[str]:
    """Deep explanation of wishlist non-purchase, optionally grounded in aggregates.

    Core product insight: a wishlist is incomplete intent. Conversion fails when
    price timing, fit uncertainty, passive saving, multi-app comparison, trust,
    occasion timing, or logistics outweigh the urge to buy within 30 days.
    Competitive lens: barriers differ by platform (apparel fit on Myntra, beauty
    trust on Nykaa, value/sale waiting on Ajio) while sale-waiting and comparison
    often appear as shared frictions.
    """
    base = [
        "Price / sale waiting - users shortlist now and delay until discounts (strong on Myntra and Ajio).",
        "Fit & sizing uncertainty - apparel wishlists stall when size charts feel inconsistent (Myntra-heavy).",
        "Passive bookmarking - inspiration saves never enter a 30-day purchase window.",
        "External / competitive comparison - checking Nykaa, Ajio, Amazon, or Flipkart before committing.",
        "Trust & authenticity - especially beauty on Nykaa; review doubt blocks checkout.",
        "Timing / occasion - saved for weddings, festivals, or later seasons.",
        "Logistics friction - delivery, returns, and stock issues reduce urgency.",
        "Competitive platform preference - users finish the journey on the app they trust for that category.",
    ]
    if not summary:
        return base

    # Prepend evidence-backed platform tops so the UI reflects live aggregates.
    dynamic: list[str] = []
    top_barriers = summary.get("top_barrier_by_platform") or {}
    for platform in ("myntra", "nykaa", "ajio", "other"):
        row = top_barriers.get(platform)
        if not row:
            continue
        label = str(row.get("label") or "").replace("_", " ")
        share = row.get("share")
        share_txt = f" (~{round(float(share) * 100)}% of tagged evidence)" if share is not None else ""
        dynamic.append(
            f"{platform.capitalize()} top barrier: {label}{share_txt} - "
            f"wishlist interest stalls here before 30-day purchase."
        )
    # Keep unique dynamic lines first, then foundational narrative.
    seen = set()
    out: list[str] = []
    for line in dynamic + base:
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out[:12]


def summarize_competitive(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dashboard-ready competitive summary from aggregate payloads."""
    platforms = sorted({p["platform"] for p in payloads}, key=lambda p: list(PLATFORMS).index(p) if p in PLATFORMS else 99)
    motives = [p for p in payloads if p["metric_type"] == "motive"]
    barriers = [p for p in payloads if p["metric_type"] == "barrier"]

    shared_motives = sorted({p["label"] for p in motives if p["shared_vs_unique"] == "shared"})
    unique_by_platform: dict[str, list[str]] = defaultdict(list)
    for p in motives:
        if p["shared_vs_unique"] == "unique_to_platform":
            unique_by_platform[p["platform"]].append(p["label"])
    for platform, labels in unique_by_platform.items():
        unique_by_platform[platform] = sorted(set(labels))

    # Narrative helpers: top barrier per platform (why they don't buy).
    top_barriers: dict[str, dict[str, Any]] = {}
    for platform in platforms:
        platform_barriers = [b for b in barriers if b["platform"] == platform]
        if platform_barriers:
            top = max(platform_barriers, key=lambda b: b["count"])
            top_barriers[platform] = {
                "label": top["label"],
                "count": top["count"],
                "share": top["share"],
                "confidence": top["confidence"],
            }

    top_motives: dict[str, dict[str, Any]] = {}
    for platform in platforms:
        platform_motives = [m for m in motives if m["platform"] == platform]
        if platform_motives:
            top = max(platform_motives, key=lambda m: m["count"])
            top_motives[platform] = {
                "label": top["label"],
                "count": top["count"],
                "share": top["share"],
                "confidence": top["confidence"],
            }

    summary = {
        "platforms": platforms,
        "motives": motives,
        "barriers": barriers,
        "shared_motives": shared_motives,
        "unique_motives_by_platform": dict(unique_by_platform),
        "top_motive_by_platform": top_motives,
        "top_barrier_by_platform": top_barriers,
        "why_not_purchase": [],
    }
    summary["why_not_purchase"] = build_why_not_purchase_narrative(summary)
    return summary
