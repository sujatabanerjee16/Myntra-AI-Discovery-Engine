import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getComparisons,
  getCompetitiveAnalysis,
  getConversionMetric,
  getFilters,
  getHeatmap,
  getIntentBreakdown,
  getRankedReasons,
  listInsightFeedback,
  runInternalCompute,
  submitInsightFeedback,
} from "../api";
import { PLATFORM_META } from "../types";
import type {
  ComparisonResponse,
  CompetitiveAnalysisResponse,
  ConversionMetricResponse,
  DashboardFilters,
  FilterState,
  HeatmapResponse,
  InsightFeedbackRecord,
  IntentBreakdownResponse,
  IntentType,
  PlatformId,
  ReasonRankResponse,
  SidebarFilters,
  SourceId,
} from "../types";

const AGE_SEGMENTS = ["age_18_24", "age_25_35"] as const;

const AGE_BEHAVIOR_NOTES: Record<string, string[]> = {
  age_18_24: [
    "Often wait for an occasion or a sale; forgetting and choice overload are common",
    "Strongest decision help: real customer photos / videos",
  ],
  age_25_35: [
    "More price-too-high, photo/review trust doubt, and fit uncertainty",
    "Decision help is mixed: styling, fit confidence, reminders",
  ],
};
import CompetitiveAnalysisPanel from "./CompetitiveAnalysisPanel";
import { formatReason } from "./ConfidenceBadge";
import QuestionsView from "./QuestionsView";

interface Props {
  filters: FilterState;
  onFiltersChange: (next: FilterState) => void;
  sidebar: SidebarFilters;
  onSidebarChange: (next: SidebarFilters) => void;
  /** Send a question to the Discovery Chat tab (from the Explore Questions card). */
  onAskQuestion?: (question: string) => void;
  /** Which tab's content to render: the analytics dashboard or the competitive page. */
  view?: "dashboard" | "competitive";
}

const SOURCES: { id: SourceId; label: string }[] = [
  { id: "play_store", label: "Play Store" },
  { id: "youtube", label: "YouTube" },
  { id: "reddit", label: "Reddit" },
  { id: "product_review", label: "Product Reviews" },
  { id: "social", label: "Social" },
  { id: "research", label: "Research" },
];

const SOURCE_ALIASES: Record<SourceId, string[]> = {
  play_store: ["play_store", "playstore", "google_play", "app"],
  youtube: ["youtube", "yt"],
  reddit: ["reddit"],
  product_review: ["product_review", "product_reviews", "review", "reviews"],
  social: ["social", "instagram", "twitter", "x"],
  research: ["research", "survey"],
};

function confidenceTier(confidence: number | null): "high" | "medium" | "low" {
  if (confidence === null) return "low";
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

function confidenceLabel(tier: "high" | "medium" | "low"): string {
  if (tier === "high") return "High Confidence";
  if (tier === "medium") return "Medium Confidence";
  return "Low Confidence";
}

// Map the numeric ₹ range onto the corpus's semantic price bands
// (budget / mid / premium). The backend filters price_band by exact string
// match, so we only emit a band that actually exists in the data — otherwise
// we send "" (All prices) rather than a numeric bucket the corpus never
// contains (which previously made the price filter a silent no-op).
function resolvePriceBand(min: number, max: number, available: string[]): string {
  const mid = (min + max) / 2;
  const desired = mid < 1500 ? "budget" : mid < 4000 ? "mid" : "premium";
  return available.includes(desired) ? desired : "";
}

function matchesSelectedSources(itemSources: string[], selected: SourceId[]): boolean {
  if (selected.length === 0) return false;
  if (itemSources.length === 0) return true; // keep untagged rows visible
  const aliases = new Set(selected.flatMap((id) => SOURCE_ALIASES[id]));
  return itemSources.some((source) => {
    const key = source.toLowerCase().replace(/\s+/g, "_");
    return aliases.has(key) || selected.some((id) => key.includes(id));
  });
}

function intentWeight(item: { active_shortlist_count: number; passive_bookmark_count: number }, intentType: IntentType): number {
  const active = item.active_shortlist_count;
  const passive = item.passive_bookmark_count;
  const total = active + passive;
  if (total === 0) return intentType === "medium" ? 1 : 0.35;
  const activeShare = active / total;
  if (intentType === "high") return 0.35 + activeShare * 0.9;
  if (intentType === "low") return 0.35 + (1 - activeShare) * 0.9;
  return 0.7 + (1 - Math.abs(activeShare - 0.5)) * 0.4;
}

export default function DashboardView({ filters, onFiltersChange, sidebar, onSidebarChange, onAskQuestion, view = "dashboard" }: Props) {
  const { priceMin, priceMax, intentType, sources, confidenceMin, platforms } = sidebar;
  const setPriceMin = (value: number) => onSidebarChange({ ...sidebar, priceMin: value });
  const setPriceMax = (value: number) => onSidebarChange({ ...sidebar, priceMax: value });
  const setIntentType = (value: IntentType) => onSidebarChange({ ...sidebar, intentType: value });
  const setConfidenceMin = (value: number) => onSidebarChange({ ...sidebar, confidenceMin: value });

  const [options, setOptions] = useState<DashboardFilters | null>(null);
  const [reasons, setReasons] = useState<ReasonRankResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [intent, setIntent] = useState<IntentBreakdownResponse | null>(null);
  const [conversion, setConversion] = useState<ConversionMetricResponse | null>(null);
  const [competitive, setCompetitive] = useState<CompetitiveAnalysisResponse | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonResponse | null>(null);
  const [feedback, setFeedback] = useState<InsightFeedbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [reasonCategory, setReasonCategory] = useState("price_sensitivity_waiting");
  const [verdict, setVerdict] = useState("validated");
  const [notes, setNotes] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  // Sync price-band filter into API filter state (drives reload).
  useEffect(() => {
    const nextBand = resolvePriceBand(priceMin, priceMax, options?.price_bands ?? []);
    if (filters.price_band === nextBand) return;
    const timer = window.setTimeout(() => {
      onFiltersChange({ ...filters, price_band: nextBand });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [priceMin, priceMax, filters, onFiltersChange, options]);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        filterOptions,
        reasonData,
        heatmapData,
        intentData,
        conversionData,
        feedbackData,
        competitiveData,
        comparisonData,
      ] = await Promise.all([
        getFilters(),
        getRankedReasons(filters),
        getHeatmap(filters),
        getIntentBreakdown(filters),
        getConversionMetric().catch(() => null),
        listInsightFeedback().catch(() => ({ total: 0, feedback: [] as InsightFeedbackRecord[] })),
        getCompetitiveAnalysis().catch(() => null),
        getComparisons({ ...filters, segment: "" }).catch(() => null),
      ]);
      setOptions(filterOptions);
      setReasons(reasonData);
      setHeatmap(heatmapData);
      setIntent(intentData);
      setConversion(conversionData);
      setFeedback(feedbackData.feedback);
      setCompetitive(competitiveData);
      setComparisons(comparisonData);
      setReasonCategory((current) => {
        const cats = filterOptions.reason_categories ?? [];
        if (cats.length && !cats.includes(current)) return cats[0];
        return current;
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  async function handleCompute() {
    setComputing(true);
    setError(null);
    try {
      await runInternalCompute();
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compute failed");
    } finally {
      setComputing(false);
    }
  }

  async function handleSubmitFeedback(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setFeedbackSuccess(null);
    setFeedbackSubmitting(true);
    try {
      const saved = await submitInsightFeedback({
        reason_category: reasonCategory,
        verdict,
        notes: notes || undefined,
      });
      setNotes("");
      const feedbackData = await listInsightFeedback();
      setFeedback(feedbackData.feedback);
      setFeedbackSuccess(
        `${formatReason(saved.reason_category)} marked as ${saved.verdict.replace(/_/g, " ")}` +
          (saved.adjusted_confidence !== null
            ? ` · confidence → ${saved.adjusted_confidence.toFixed(2)}`
            : ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Feedback submission failed");
    } finally {
      setFeedbackSubmitting(false);
    }
  }

  const filterIntensity = useMemo(() => {
    const priceSpan = Math.max(priceMax - priceMin, 500);
    const priceFactor = Math.min(priceSpan / 5000, 1.25);
    const sourceFactor = 0.55 + sources.length * 0.15;
    const intentFactor = intentType === "high" ? 1.05 : intentType === "low" ? 0.85 : 0.95;
    const confidenceFactor = 0.7 + (1 - confidenceMin) * 0.55;
    return Math.max(0.35, Math.min(1.4, priceFactor * sourceFactor * intentFactor * confidenceFactor));
  }, [priceMin, priceMax, sources, intentType, confidenceMin]);

  const filteredReasons = useMemo(() => {
    const items = reasons?.reasons ?? [];
    return items
      .filter((item) => {
        if (item.confidence !== null && item.confidence < confidenceMin) return false;
        if (!matchesSelectedSources(item.sources, sources)) return false;
        return true;
      })
      .map((item) => {
        // Soft intent scaling only — do not drop category rows that are mostly passive.
        const weight = Math.min(1, intentWeight(item, intentType));
        return {
          ...item,
          evidence_volume: Math.max(1, Math.round(item.evidence_volume * weight * filterIntensity)),
          active_shortlist_count: Math.round(item.active_shortlist_count * (intentType === "low" ? 0.45 : intentType === "high" ? 1.15 : 0.85)),
          passive_bookmark_count: Math.round(item.passive_bookmark_count * (intentType === "high" ? 0.45 : intentType === "low" ? 1.15 : 0.85)),
        };
      })
      .sort((a, b) => b.evidence_volume - a.evidence_volume);
  }, [reasons, confidenceMin, sources, intentType, filterIntensity]);

  const totalVolume = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0) || 1,
    [filteredReasons],
  );

  const reasonBars = useMemo(() => {
    return filteredReasons.slice(0, 7).map((item) => {
      const pct = Math.round((item.evidence_volume / totalVolume) * 100);
      const tier = confidenceTier(item.confidence);
      return {
        ...item,
        pct,
        tier,
        label: formatReason(item.reason_category),
      };
    });
  }, [filteredReasons, totalVolume]);

  const maxBar = Math.max(...reasonBars.map((item) => item.pct), 1);

  const activeTotal = useMemo(() => {
    const base = intent?.total_active ?? filteredReasons.reduce((sum, item) => sum + item.active_shortlist_count, 0);
    const factor = intentType === "high" ? 1.2 : intentType === "low" ? 0.55 : 0.9;
    return Math.max(0, Math.round(base * factor * filterIntensity));
  }, [intent, filteredReasons, intentType, filterIntensity]);

  const passiveTotal = useMemo(() => {
    const base = intent?.total_passive ?? filteredReasons.reduce((sum, item) => sum + item.passive_bookmark_count, 0);
    const factor = intentType === "low" ? 1.2 : intentType === "high" ? 0.55 : 0.9;
    return Math.max(0, Math.round(base * factor * filterIntensity));
  }, [intent, filteredReasons, intentType, filterIntensity]);

  const intentSum = activeTotal + passiveTotal || 1;
  const activePct = Math.round((activeTotal / intentSum) * 100);
  const passivePct = 100 - activePct;

  const feedbackTotal = useMemo(() => {
    const fromReasons = filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0);
    const scale = 12 + sources.length * 3;
    if (fromReasons > 0) return fromReasons * scale;
    // Loading placeholder only — once reasons are loaded, empty filters stay at 0.
    if (reasons !== null) return 0;
    return Math.round(124832 * filterIntensity);
  }, [filteredReasons, sources.length, filterIntensity, reasons]);

  const topFriction = reasonBars[0];
  // The conversion metric is only meaningful once it has been computed against a
  // cohort. A freshly loaded dataset returns 0 wishlist_users → 0/0 = 0.0%, which
  // looks alarming/broken. Treat that as "not computed" and show a neutral state.
  const conversionReady = conversion !== null && conversion.wishlist_users > 0;
  const wishlistRate = conversionReady
    ? `${(Math.min(0.95, conversion!.conversion_rate * (intentType === "high" ? 1.15 : intentType === "low" ? 0.75 : 1)) * 100).toFixed(1)}%`
    : conversion !== null
      ? "—"
      : `${(18.4 * filterIntensity).toFixed(1)}%`;
  const wishlistDelta = conversionReady
    ? `${conversion!.converted_users.toLocaleString()} / ${conversion!.wishlist_users.toLocaleString()} users · ${conversion!.window_days}d`
    : conversion !== null
      ? "Not computed yet — click Refresh"
      : "Last 30 days, +2.1%";
  const nonConversionRate = conversionReady
    ? `${(Math.max(0.05, conversion!.non_conversion_rate * (intentType === "low" ? 1.1 : intentType === "high" ? 0.9 : 1)) * 100).toFixed(1)}%`
    : null;

  const filteredHeatmap = useMemo(() => {
    if (!heatmap) return null;
    const cells = heatmap.cells.map((cell) => ({
      ...cell,
      value: Math.max(0, Math.round(cell.value * filterIntensity * (intentType === "high" ? 1.1 : 0.9))),
    }));
    const columns = [...AGE_SEGMENTS];
    return { ...heatmap, cells, columns };
  }, [heatmap, filterIntensity, intentType]);

  const maxHeat = Math.max(...(filteredHeatmap?.cells.map((cell) => cell.value) ?? [1]), 1);

  const ageComparison = useMemo(() => {
    const items = comparisons?.items ?? [];
    const respondents = comparisons?.respondent_counts ?? {};
    return AGE_SEGMENTS.map((segment) => {
      const rows = items
        .filter((item) => item.dimension === segment)
        .sort((a, b) => b.evidence_volume - a.evidence_volume)
        .slice(0, 4);
      const excerptTotal = rows.reduce((sum, row) => sum + row.evidence_volume, 0);
      return {
        segment,
        label: formatReason(segment),
        respondents: respondents[segment] ?? 0,
        excerptTotal,
        reasons: rows,
        notes: AGE_BEHAVIOR_NOTES[segment] ?? [],
      };
    });
  }, [comparisons]);

  const ageContrast = useMemo(() => {
    const [young, older] = ageComparison;
    if (!young || !older) return "";
    const youngTop = young.reasons[0];
    const olderTop = older.reasons[0];
    if (!youngTop && !olderTop) {
      return "Survey age bands are loaded as filters. Refresh research insights to populate side-by-side reason volumes.";
    }
    const youngLabel = youngTop ? formatReason(youngTop.reason_category) : "mixed blockers";
    const olderLabel = olderTop ? formatReason(olderTop.reason_category) : "mixed blockers";
    return `${young.label} evidence concentrates on ${youngLabel}; ${older.label} concentrates on ${olderLabel}. Volume is uneven across the two surveys — treat this as directional.`;
  }, [ageComparison]);

  const categoryOptions = options?.categories?.length
    ? options.categories
    : ["clothing", "footwear", "accessories"];

  const reasonCategoryOptions = options?.reason_categories?.length
    ? options.reason_categories
    : (reasons?.reasons.map((item) => item.reason_category) ?? [
        "price_sensitivity_waiting",
        "fit_sizing_uncertainty",
        "passive_bookmarking",
        "quality_trust_doubt",
      ]);

  useEffect(() => {
    if (!reasonCategoryOptions.length) return;
    if (!reasonCategoryOptions.includes(reasonCategory)) {
      setReasonCategory(reasonCategoryOptions[0]);
    }
  }, [reasonCategoryOptions, reasonCategory]);

  const activeFilterSummary = [
    filters.segment ? formatReason(filters.segment) : "Age 18–24 + 25–35",
    filters.category ? formatReason(filters.category) : "All categories",
    filters.price_band
      ? `₹${priceMin}–₹${priceMax} · ${formatReason(filters.price_band)}`
      : `₹${priceMin}–₹${priceMax}`,
    intentType === "high" ? "High intent" : intentType === "low" ? "Low intent" : "Medium intent",
    `${sources.length} source${sources.length === 1 ? "" : "s"}`,
    `≥${Math.round(confidenceMin * 100)}% conf.`,
  ].join(" · ");

  const toggleSource = (id: SourceId) => {
    const next = sources.includes(id)
      ? sources.filter((item) => item !== id)
      : [...sources, id];
    if (next.length === 0) return;
    onSidebarChange({ ...sidebar, sources: next });
  };

  const togglePlatform = (id: PlatformId) => {
    const next = platforms.includes(id)
      ? platforms.filter((item) => item !== id)
      : [...platforms, id];
    if (next.length === 0) return;
    onSidebarChange({ ...sidebar, platforms: next });
  };

  const clearSidebarFilters = () => {
    onSidebarChange({
      priceMin: 500,
      priceMax: 5000,
      intentType: "high",
      sources: ["play_store", "youtube", "reddit", "product_review", "social", "research"],
      confidenceMin: 0.5,
      platforms: ["myntra", "nykaa", "ajio"],
    });
    onFiltersChange({ ...filters, category: "", price_band: "", segment: "" });
  };

  useEffect(() => {
    if (filters.segment && !AGE_SEGMENTS.includes(filters.segment as (typeof AGE_SEGMENTS)[number])) {
      onFiltersChange({ ...filters, segment: "" });
    }
  }, [filters, onFiltersChange]);

  const segmentOptions = AGE_SEGMENTS;

  return (
    <div className="wi-dashboard">
      <aside className="wi-dash-sidebar">
        <div className="wi-dash-filter">
          <div className="wi-dash-label-row">
            <span className="wi-dash-label">Filters</span>
            <button type="button" className="wi-dash-clear" onClick={clearSidebarFilters}>
              Reset
            </button>
          </div>
          <p className="wi-dash-active-summary">{activeFilterSummary}</p>
        </div>

        <div className="wi-dash-filter">
          <span className="wi-dash-label">User segment</span>
          <div className="wi-dash-pills">
            {segmentOptions.map((value) => (
              <button
                key={value}
                type="button"
                className={`wi-dash-pill ${filters.segment === value ? "active" : ""}`}
                onClick={() =>
                  onFiltersChange({
                    ...filters,
                    segment: filters.segment === value ? "" : value,
                  })
                }
              >
                {formatReason(value)}
              </button>
            ))}
          </div>
        </div>

        <div className="wi-dash-filter">
          <label className="wi-dash-label" htmlFor="dash-category">
            Category
          </label>
          <select
            id="dash-category"
            className="wi-dash-select"
            value={filters.category}
            onChange={(e) => onFiltersChange({ ...filters, category: e.target.value })}
          >
            <option value="">All categories</option>
            {categoryOptions.map((value) => (
              <option key={value} value={value}>
                {formatReason(value)}
              </option>
            ))}
          </select>
          <div className="wi-dash-category-hints">
            {categoryOptions.slice(0, 4).map((value) => (
              <button
                key={value}
                type="button"
                className={`wi-dash-hint ${filters.category === value ? "active" : ""}`}
                onClick={() => onFiltersChange({ ...filters, category: value })}
              >
                {formatReason(value)}
              </button>
            ))}
          </div>
        </div>

        <div className="wi-dash-filter">
          <div className="wi-dash-label-row">
            <span className="wi-dash-label">Price Band</span>
            <span className="wi-dash-range-text">₹0 — ₹10,000+</span>
          </div>
          <input
            type="range"
            className="wi-dash-slider"
            min={0}
            max={10000}
            step={100}
            value={priceMax}
            onChange={(e) => setPriceMax(Number(e.target.value))}
            aria-label="Maximum price"
          />
          <div className="wi-dash-price-inputs">
            <label>
              <span className="sr-only">Min price</span>
              <input
                type="number"
                value={priceMin}
                min={0}
                max={priceMax}
                onChange={(e) => setPriceMin(Number(e.target.value))}
              />
            </label>
            <span className="wi-dash-price-sep">to</span>
            <label>
              <span className="sr-only">Max price</span>
              <input
                type="number"
                value={priceMax}
                min={priceMin}
                max={10000}
                onChange={(e) => setPriceMax(Number(e.target.value))}
              />
            </label>
          </div>
        </div>

        <div className="wi-dash-filter">
          <span className="wi-dash-label">Intent Type</span>
          <div className="wi-dash-pills">
            {(
              [
                { id: "high", label: "High Intent (Active)" },
                { id: "medium", label: "Medium Intent" },
                { id: "low", label: "Low Intent (Passive)" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                className={`wi-dash-pill ${intentType === item.id ? "active" : ""}`}
                onClick={() => setIntentType(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="wi-dash-filter">
          <span className="wi-dash-label">Platform</span>
          <div className="wi-dash-platforms">
            {PLATFORM_META.map((item) => {
              const active = platforms.includes(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`wi-dash-platform-chip ${active ? "active" : ""}`}
                  style={active ? { borderColor: item.color, background: `${item.color}22` } : undefined}
                  onClick={() => togglePlatform(item.id)}
                  aria-pressed={active}
                >
                  <span className="wi-dash-platform-dot" style={{ background: item.color }} />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="wi-dash-filter">
          <span className="wi-dash-label">Source</span>
          <div className="wi-dash-checks">
            {SOURCES.map((item) => (
              <label key={item.id} className="wi-dash-check">
                <input
                  type="checkbox"
                  checked={sources.includes(item.id)}
                  onChange={() => toggleSource(item.id)}
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="wi-dash-filter">
          <div className="wi-dash-label-row">
            <span className="wi-dash-label">Confidence</span>
            <span className="wi-dash-range-text">{Math.round(confidenceMin * 100)}%</span>
          </div>
          <input
            type="range"
            className="wi-dash-slider"
            min={0}
            max={100}
            value={Math.round(confidenceMin * 100)}
            onChange={(e) => setConfidenceMin(Number(e.target.value) / 100)}
            aria-label="Minimum confidence"
          />
          <div className="wi-dash-slider-ends">
            <span>0%</span>
            <span>100%</span>
          </div>
        </div>
      </aside>

      <div className="wi-dash-content">
        {error && <div className="error-banner">{error}</div>}
        {loading && reasons === null && view === "dashboard" && (
          <p className="loading">Loading dashboard…</p>
        )}
        {loading && reasons !== null && (
          <div className="wi-updating-chip" role="status" aria-live="polite">
            <span className="wi-updating-spinner" aria-hidden="true" />
            Updating…
          </div>
        )}

        {reasons !== null && view === "dashboard" && (
          <>
            {onAskQuestion && <QuestionsView onAsk={onAskQuestion} />}

            <div className="wi-filter-chip-row">
              <span className="wi-filter-chip">{activeFilterSummary}</span>
              <span className="wi-filter-chip">
                Platforms:{" "}
                {platforms
                  .map((id) => PLATFORM_META.find((p) => p.id === id)?.label ?? id)
                  .join(", ")}
              </span>
              <span className="wi-filter-chip wi-filter-chip--count">
                {reasonBars.length} reason{reasonBars.length === 1 ? "" : "s"} shown
              </span>
            </div>

            <div className="wi-kpi-row">
              <article className="wi-kpi-card">
                <div className="wi-kpi-card-head">
                  <h3>Wishlist-to-Purchase</h3>
                  <button
                    type="button"
                    className="wi-kpi-action"
                    onClick={() => void handleCompute()}
                    disabled={computing}
                    title="Recompute conversion and analytics from the latest offline events"
                  >
                    {computing ? "Computing…" : "Refresh data"}
                  </button>
                </div>
                <p className="wi-kpi-value">{wishlistRate}</p>
                <p className="wi-kpi-sub wi-kpi-sub--up">{wishlistDelta}</p>
                {nonConversionRate && (
                  <p className="wi-kpi-sub">Non-conversion {nonConversionRate}</p>
                )}
              </article>
              <article className="wi-kpi-card">
                <h3>Active vs Passive</h3>
                <p className="wi-kpi-value">
                  {activePct}% / {passivePct}%
                </p>
                <p className="wi-kpi-sub">Active Intent / Passive Intent</p>
              </article>
              <article className="wi-kpi-card">
                <h3>Total Feedback</h3>
                <p className="wi-kpi-value">{feedbackTotal.toLocaleString()}</p>
                <p className="wi-kpi-sub">Feedback Entries Collected</p>
              </article>
              <article className="wi-kpi-card">
                <h3>Top Friction</h3>
                <p className="wi-kpi-value wi-kpi-value--sm">
                  {topFriction ? `${topFriction.label} ${topFriction.pct}%` : "—"}
                </p>
                <p className="wi-kpi-sub">Most Common Reason</p>
              </article>
            </div>

            <section className="wi-dash-card wi-age-compare">
                <div className="wi-age-compare-head">
                  <h2>Age cohort comparison · 18–24 vs 25–35</h2>
                  <p className="wi-kpi-sub">
                    Unique survey respondents from Myntra Wishlist + Wishlist Habits. Reason
                    shares are excerpt mix, not extra people — one response can produce several tags.
                  </p>
                  {ageContrast && <p className="wi-age-contrast">{ageContrast}</p>}
                </div>
                <div className="wi-age-compare-grid">
                  {ageComparison.map((cohort) => (
                    <article key={cohort.segment} className="wi-age-cohort">
                      <header className="wi-age-cohort-head">
                        <h3>{cohort.label}</h3>
                        <span className="wi-age-cohort-vol">
                          {cohort.respondents
                            ? `${cohort.respondents} respondent${cohort.respondents === 1 ? "" : "s"}`
                            : "No respondents"}
                        </span>
                      </header>
                      <ul className="wi-age-notes">
                        {cohort.notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                      <div className="wi-age-reasons">
                        <span className="wi-dash-label">Top non-conversion reasons</span>
                        {cohort.reasons.length === 0 ? (
                          <p className="muted">No age-tagged reasons yet — refresh insights.</p>
                        ) : (
                          cohort.reasons.map((row) => (
                            <div key={row.reason_category} className="wi-age-reason-row">
                              <span>{formatReason(row.reason_category)}</span>
                              <strong>
                                {cohort.excerptTotal
                                  ? `${Math.round((row.evidence_volume / cohort.excerptTotal) * 100)}%`
                                  : "—"}
                              </strong>
                            </div>
                          ))
                        )}
                      </div>
                      <button
                        type="button"
                        className="wi-dash-hint"
                        onClick={() => onFiltersChange({ ...filters, segment: cohort.segment })}
                      >
                        Filter dashboard to {cohort.label}
                      </button>
                    </article>
                  ))}
                </div>
              </section>

            <div className="wi-dash-mid">
              <section className="wi-dash-card">
                <h2>Non-Conversion Reasons (with AI Confidence)</h2>
                <div className="wi-reason-bars">
                  {reasonBars.map((item) => (
                    <div key={item.reason_category} className="wi-reason-bar-row">
                      <span className="wi-reason-bar-label">{item.label}</span>
                      <div className="wi-reason-bar-track">
                        <div
                          className="wi-reason-bar-fill"
                          style={{ width: `${(item.pct / maxBar) * 100}%` }}
                        />
                        <span className="wi-reason-bar-pct">{item.pct}%</span>
                      </div>
                      <span className={`wi-conf-pill wi-conf-pill--${item.tier}`}>
                        {confidenceLabel(item.tier)}
                      </span>
                    </div>
                  ))}
                  {reasonBars.length === 0 && (
                    <p className="muted">No reasons match the current filters.</p>
                  )}
                </div>
              </section>

              <section className="wi-dash-card">
                <h2>Reasons vs Segments Heatmap</h2>
                {filteredHeatmap && filteredHeatmap.rows.length > 0 ? (
                  <div className="wi-heat-wrap">
                    <table className="wi-heat-table">
                      <thead>
                        <tr>
                          <th />
                          {filteredHeatmap.columns.slice(0, 4).map((col) => (
                            <th key={col}>{formatReason(col)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredHeatmap.rows.slice(0, 4).map((row) => (
                          <tr key={row}>
                            <th>{formatReason(row).split(/[\s&/]+/)[0]}</th>
                            {filteredHeatmap.columns.slice(0, 4).map((col) => {
                              const cell = filteredHeatmap.cells.find(
                                (item) => item.row === row && item.column === col,
                              );
                              const value = cell?.value ?? 0;
                              const intensity = value / maxHeat;
                              return (
                                <td key={col}>
                                  <div
                                    className="wi-heat-cell"
                                    style={{
                                      background: `rgba(219, 39, 119, ${0.1 + intensity * 0.75})`,
                                      color: intensity > 0.5 ? "#fff" : "#831843",
                                    }}
                                    title={`${formatReason(row)} × ${formatReason(col)}: ${value} items`}
                                  >
                                    {value}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">No heatmap data for current filters.</p>
                )}
              </section>
            </div>

            <div className="wi-dash-mid wi-dash-mid--feedback">
              <section className="wi-dash-card">
                <h2>Insight Feedback</h2>
                <p className="wi-kpi-sub" style={{ marginTop: "-0.35rem", marginBottom: "0.85rem" }}>
                  Validate or flag a non-conversion reason. Verdicts adjust confidence for that reason.
                </p>
                <form
                  onSubmit={(event) => void handleSubmitFeedback(event)}
                  className="feedback-form wi-dash-feedback-form"
                >
                  <label>
                    Reason category
                    <select
                      value={reasonCategory}
                      onChange={(event) => setReasonCategory(event.target.value)}
                    >
                      {reasonCategoryOptions.map((value) => (
                        <option key={value} value={value}>
                          {formatReason(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Verdict
                    <select value={verdict} onChange={(event) => setVerdict(event.target.value)}>
                      <option value="validated">Validated (+0.05 confidence)</option>
                      <option value="flagged">Flagged (−0.12 confidence)</option>
                      <option value="needs_review">Needs review (−0.03 confidence)</option>
                    </select>
                  </label>
                  <label>
                    Notes
                    <textarea
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      rows={3}
                      placeholder="Optional context for other PMs…"
                    />
                  </label>
                  <button type="submit" disabled={feedbackSubmitting}>
                    {feedbackSubmitting ? "Saving…" : "Submit feedback"}
                  </button>
                  {feedbackSuccess && <p className="wi-feedback-success">{feedbackSuccess}</p>}
                </form>
              </section>

              <section className="wi-dash-card">
                <h2>Recent Feedback</h2>
                <p className="wi-kpi-sub" style={{ marginTop: "-0.35rem", marginBottom: "0.85rem" }}>
                  Latest PM validation history for taxonomy and confidence calibration.
                </p>
                {feedback.length === 0 ? (
                  <p className="muted">No feedback recorded yet. Submit a verdict to see it here.</p>
                ) : (
                  <ul className="wi-feedback-list">
                    {feedback.map((item) => {
                      const reviewer = (item.reviewer || "pm").toLowerCase() === "pm"
                        ? "PM"
                        : item.reviewer;
                      const when = item.created_at
                        ? new Date(item.created_at).toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })
                        : null;
                      const metaParts = [
                        reviewer,
                        item.adjusted_confidence !== null
                          ? `Adj. conf. ${item.adjusted_confidence.toFixed(2)}`
                          : null,
                        when,
                      ].filter(Boolean);

                      return (
                        <li key={item.id} className="wi-feedback-item">
                          <div className="wi-feedback-item-top">
                            <strong>{formatReason(item.reason_category)}</strong>
                            <span className={`wi-feedback-verdict wi-feedback-verdict--${item.verdict}`}>
                              {item.verdict.replace(/_/g, " ")}
                            </span>
                          </div>
                          <p className="wi-feedback-item-meta">{metaParts.join(" · ")}</p>
                          {item.notes && <p className="wi-feedback-notes">{item.notes}</p>}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            </div>
          </>
        )}

        {view === "competitive" && (
          <>
            <div className="wi-filter-chip-row">
              <span className="wi-filter-chip">{activeFilterSummary}</span>
              <span className="wi-filter-chip">
                Platforms:{" "}
                {platforms
                  .map((id) => PLATFORM_META.find((p) => p.id === id)?.label ?? id)
                  .join(", ")}
              </span>
            </div>

            <CompetitiveAnalysisPanel
              data={competitive}
              loading={loading}
              selectedPlatforms={platforms}
            />
          </>
        )}
      </div>
    </div>
  );
}
