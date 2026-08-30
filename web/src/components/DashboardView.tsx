import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getComparisons,
  getCompetitiveAnalysis,
  getConversionMetric,
  getCorpusStats,
  getFilters,
  getRankedReasons,
  getSurveyHabits,
  listInsightFeedback,
  submitInsightFeedback,
} from "../api";
import { PLATFORM_META } from "../types";
import type {
  ComparisonResponse,
  CompetitiveAnalysisResponse,
  ConversionMetricResponse,
  CorpusScrapeStats,
  DashboardFilters,
  FilterState,
  InsightFeedbackRecord,
  IntentType,
  PlatformId,
  ReasonRankResponse,
  SidebarFilters,
  SourceId,
  SurveyHabitsResponse,
} from "../types";

const AGE_SEGMENTS = ["age_18_24", "age_25_35"] as const;

const SOURCE_SCRAPE_LABELS: Record<string, string> = {
  play_store: "Play Store",
  reddit: "Reddit",
  youtube: "YouTube",
  product_review: "Product reviews",
  social: "Social",
  research: "Research surveys",
};

/** Last-resort survey sizes when the API omits respondent_counts. */
const AGE_RESPONDENT_FALLBACK: Record<(typeof AGE_SEGMENTS)[number], number> = {
  age_18_24: 27,
  age_25_35: 15,
};

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

function matchesIntent(
  item: { active_shortlist_count: number; passive_bookmark_count: number },
  intentType: IntentType,
): boolean {
  if (intentType === "medium") return true;
  const active = item.active_shortlist_count;
  const passive = item.passive_bookmark_count;
  if (intentType === "high") return active >= passive;
  return passive > active;
}

export default function DashboardView({ filters, onFiltersChange, sidebar, onSidebarChange, onAskQuestion, view = "dashboard" }: Props) {
  const { priceMin, priceMax, intentType, sources, confidenceMin, platforms } = sidebar;
  const setPriceMin = (value: number) => onSidebarChange({ ...sidebar, priceMin: value });
  const setPriceMax = (value: number) => onSidebarChange({ ...sidebar, priceMax: value });
  const setIntentType = (value: IntentType) => onSidebarChange({ ...sidebar, intentType: value });
  const setConfidenceMin = (value: number) => onSidebarChange({ ...sidebar, confidenceMin: value });

  const [options, setOptions] = useState<DashboardFilters | null>(null);
  const [reasons, setReasons] = useState<ReasonRankResponse | null>(null);
  const [conversion, setConversion] = useState<ConversionMetricResponse | null>(null);
  const [competitive, setCompetitive] = useState<CompetitiveAnalysisResponse | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonResponse | null>(null);
  const [surveyHabits, setSurveyHabits] = useState<SurveyHabitsResponse | null>(null);
  const [corpusStats, setCorpusStats] = useState<CorpusScrapeStats | null>(null);
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
        conversionData,
        feedbackData,
        competitiveData,
        comparisonData,
        habitsData,
        scrapeData,
      ] = await Promise.all([
        getFilters(),
        getRankedReasons(filters),
        getConversionMetric().catch(() => null),
        listInsightFeedback().catch(() => ({ total: 0, feedback: [] as InsightFeedbackRecord[] })),
        getCompetitiveAnalysis().catch(() => null),
        getComparisons({ ...filters, segment: "" }).catch(() => null),
        getSurveyHabits(filters.segment || undefined).catch(() => null),
        getCorpusStats().catch(() => null),
      ]);
      setOptions(filterOptions);
      setReasons(reasonData);
      setConversion(conversionData);
      setFeedback(feedbackData.feedback);
      setCompetitive(competitiveData);
      setComparisons(comparisonData);
      setSurveyHabits(habitsData);
      setCorpusStats(scrapeData);
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
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reload failed");
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

  const sourceFilteredReasons = useMemo(() => {
    return (reasons?.reasons ?? [])
      .filter((item) => {
        if (item.confidence !== null && item.confidence < confidenceMin) return false;
        if (!matchesSelectedSources(item.sources, sources)) return false;
        return true;
      })
      .sort((a, b) => b.evidence_volume - a.evidence_volume);
  }, [reasons, confidenceMin, sources]);

  const intentMatchedReasons = useMemo(
    () => sourceFilteredReasons.filter((item) => matchesIntent(item, intentType)),
    [sourceFilteredReasons, intentType],
  );

  const intentFallback =
    intentType !== "medium" && intentMatchedReasons.length === 0 && sourceFilteredReasons.length > 0;

  const filteredReasons = intentFallback ? sourceFilteredReasons : intentMatchedReasons;

  const totalVolume = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0) || 1,
    [filteredReasons],
  );

  const reasonBars = useMemo(() => {
    return filteredReasons.slice(0, 5).map((item) => {
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

  const activeTotal = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.active_shortlist_count, 0),
    [filteredReasons],
  );

  const passiveTotal = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.passive_bookmark_count, 0),
    [filteredReasons],
  );

  const intentSum = activeTotal + passiveTotal;
  const activePct = intentSum ? Math.round((activeTotal / intentSum) * 100) : 0;
  const passivePct = intentSum ? 100 - activePct : 0;

  const evidenceTotal = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0),
    [filteredReasons],
  );

  const topFriction =
    reasonBars.find((item) => item.reason_category !== "passive_bookmarking") ?? reasonBars[0];
  // Seed file data/seeds/internal_wishlist_events.json is 16 rows (10 wishlist users).
  // Do not show that demo cohort as a live conversion rate.
  const conversionReady =
    conversion !== null && conversion.wishlist_users > 16 && conversion.wishlist_users > 0;
  const wishlistRate = conversionReady
    ? `${(conversion!.conversion_rate * 100).toFixed(1)}%`
    : surveyHabits
      ? `${surveyHabits.respondents} respondents`
      : "No rate";
  const excerptScopeNote = [
    reasons?.scope_note,
    intentFallback
      ? intentType === "high"
        ? "No high-intent excerpts in this slice — showing all intents"
        : "No low-intent excerpts in this slice — showing all intents"
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const excerptFilterLabel = [
    filters.segment ? formatReason(filters.segment) : null,
    filters.category ? formatReason(filters.category) : null,
    intentType === "high" && !intentFallback ? "High intent" : null,
    intentType === "low" && !intentFallback ? "Low intent" : null,
  ]
    .filter(Boolean)
    .join(" + ");

  const wishlistDelta = conversionReady
    ? `${conversion!.converted_users.toLocaleString()} / ${conversion!.wishlist_users.toLocaleString()} users · ${conversion!.window_days}d`
    : filters.segment
      ? `Self-reported ${formatReason(filters.segment)} survey answers — category and intent do not apply`
      : "Self-reported survey answers — not a checkout conversion rate";
  const nonConversionRate = conversionReady
    ? `${(conversion!.non_conversion_rate * 100).toFixed(1)}%`
    : null;

  const ageComparison = useMemo(() => {
    const items = comparisons?.items ?? [];
    const respondents = comparisons?.respondent_counts ?? {};
    return AGE_SEGMENTS.map((segment) => {
      const rows = items
        .filter((item) => item.dimension === segment)
        .sort((a, b) => b.evidence_volume - a.evidence_volume)
        .slice(0, 4);
      const excerptTotal = rows.reduce((sum, row) => sum + row.evidence_volume, 0);
      const fromApi = Number(respondents[segment] ?? 0);
      return {
        segment,
        label: formatReason(segment),
        respondents: fromApi || (rows.length ? AGE_RESPONDENT_FALLBACK[segment] : 0),
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
      intentType: "medium",
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
                onClick={() =>
                  onFiltersChange({
                    ...filters,
                    category: filters.category === value ? "" : value,
                  })
                }
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

            {corpusStats && (
              <section className="wi-scrape-panel" aria-label="Scraped corpus volume by source">
                <div className="wi-scrape-totals">
                  <p className="wi-scrape-kicker">Corpus</p>
                  <div className="wi-scrape-total-pair">
                    <div>
                      <p className="wi-scrape-hero">{corpusStats.documents.toLocaleString()}</p>
                      <p className="wi-scrape-hero-label">Items scraped</p>
                    </div>
                    <div>
                      <p className="wi-scrape-hero">{corpusStats.chunks.toLocaleString()}</p>
                      <p className="wi-scrape-hero-label">Items classified</p>
                    </div>
                  </div>
                </div>
                <ul className="wi-scrape-sources">
                  {corpusStats.by_source.map((row) => {
                    const active = sources.includes(row.source as SourceId);
                    const share = corpusStats.documents
                      ? Math.round((row.documents / corpusStats.documents) * 100)
                      : 0;
                    return (
                      <li
                        key={row.source}
                        className={`wi-scrape-source${active ? "" : " wi-scrape-source--off"}`}
                      >
                        <div className="wi-scrape-source-top">
                          <span>{SOURCE_SCRAPE_LABELS[row.source] ?? formatReason(row.source)}</span>
                          <strong>
                            {row.documents.toLocaleString()}
                            <em>{share}%</em>
                          </strong>
                        </div>
                        <div className="wi-scrape-source-track" aria-hidden="true">
                          <div
                            className="wi-scrape-source-fill"
                            style={{ width: `${Math.max(share, 4)}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            <div className="wi-insight-grid">
              <article className="wi-kpi-card">
                <div className="wi-kpi-card-head">
                  <h3>Wishlist-to-Purchase</h3>
                  <button
                    type="button"
                    className="wi-kpi-action"
                    onClick={() => void handleCompute()}
                    disabled={computing}
                    title="Reload insights from the scraped corpus export"
                  >
                    {computing ? "Reloading…" : "Reload"}
                  </button>
                </div>
                <p className={`wi-kpi-value${conversionReady ? "" : " wi-kpi-value--sm"}`}>
                  {wishlistRate}
                </p>
                <p className="wi-kpi-sub">{wishlistDelta}</p>
                {nonConversionRate && (
                  <p className="wi-kpi-sub">Non-conversion {nonConversionRate}</p>
                )}
                {!conversionReady && surveyHabits && (
                  <ul className="wi-survey-habits">
                    {surveyHabits.workbooks.map((book) => (
                      <li key={book.file}>
                        <strong>
                          {book.file.replace(/\.xlsx$/i, "")} · n={book.n}
                        </strong>
                        <span>
                          {book.answers
                            .map((item) => `${item.count} ${item.label}`)
                            .join(" · ") || "No answers in this filter"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
              <div className="wi-insight-metrics">
                <article className="wi-kpi-card">
                  <h3>User intent</h3>
                  <p className="wi-kpi-value">
                    {intentSum ? `${activePct}% / ${passivePct}%` : "—"}
                  </p>
                  <p className="wi-kpi-sub">
                    {intentSum
                      ? excerptScopeNote || `${activeTotal} buy-soon · ${passiveTotal} bookmark-later excerpts`
                      : excerptFilterLabel
                        ? `No tagged excerpts for ${excerptFilterLabel}`
                        : "No tagged excerpts in this filter"}
                  </p>
                  {intentSum > 0 && (
                    <div className="wi-intent-track" aria-hidden="true">
                      <div className="wi-intent-fill" style={{ width: `${activePct}%` }} />
                    </div>
                  )}
                </article>
                <article className="wi-kpi-card">
                  <h3>Evidence excerpts</h3>
                  <p className="wi-kpi-value">{evidenceTotal.toLocaleString()}</p>
                  <p className="wi-kpi-sub">
                  {evidenceTotal
                    ? excerptScopeNote || "Tagged chunks in the current filter — not people"
                    : excerptFilterLabel
                      ? `No tagged chunks for ${excerptFilterLabel}`
                      : "Tagged chunks in the current filter — not people"}
                </p>
                </article>
                <article className="wi-kpi-card">
                  <h3>Top Friction</h3>
                  <p className="wi-kpi-value wi-kpi-value--sm">
                    {topFriction ? `${topFriction.label} ${topFriction.pct}%` : "—"}
                  </p>
                  <p className="wi-kpi-sub">
                  Highest-volume blocker — not save-for-later / no-intent bookmarking
                </p>
                </article>
              </div>
            </div>

            <section className="wi-dash-card wi-age-compare">
                <div className="wi-age-compare-head">
                  <h2>Age cohort comparison · 18–24 vs 25–35</h2>
                  <p className="wi-age-scope-note">
                    Always compares both age bands. The User segment filter scopes KPIs, reasons,
                    and the heatmap — not this card.
                  </p>
                  <p className="wi-kpi-sub">
                    Unique survey respondents from Myntra Wishlist + Wishlist Habits. Reason
                    shares are excerpt mix, not extra people — one response can produce several tags.
                  </p>
                  {ageContrast && <p className="wi-age-contrast">{ageContrast}</p>}
                </div>
                <div className="wi-age-compare-grid">
                  {ageComparison.map((cohort) => {
                    const selected = filters.segment === cohort.segment;
                    const otherSelected = Boolean(filters.segment) && !selected;
                    return (
                    <article
                      key={cohort.segment}
                      className={`wi-age-cohort${selected ? " wi-age-cohort--active" : ""}${otherSelected ? " wi-age-cohort--muted" : ""}`}
                    >
                      <header className="wi-age-cohort-head">
                        <h3>{cohort.label}</h3>
                        <span className="wi-age-cohort-vol">
                          {selected ? "Sidebar filter · " : ""}
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
                        className={`wi-dash-hint${selected ? " active" : ""}`}
                        onClick={() =>
                          onFiltersChange({
                            ...filters,
                            segment: selected ? "" : cohort.segment,
                          })
                        }
                      >
                        {selected
                          ? `Clear ${cohort.label} filter`
                          : `Filter dashboard to ${cohort.label}`}
                      </button>
                    </article>
                    );
                  })}
                </div>
              </section>

            <section className="wi-dash-card">
              <h2>Why wishlists do not convert</h2>
              <p className="wi-kpi-sub" style={{ marginTop: "-0.55rem", marginBottom: "0.9rem" }}>
                Top reasons from scraped reviews, social posts, and survey answers
              </p>
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

            <details className="wi-dash-card wi-pm-calibrate">
              <summary>
                PM calibration
                <span>
                  {feedback.length
                    ? `${feedback.length} note${feedback.length === 1 ? "" : "s"}`
                    : "Optional"}
                </span>
              </summary>
              <p className="wi-kpi-sub">
                Internal only — not scraped user data. Use this to validate or flag a reason.
              </p>
              <div className="wi-pm-calibrate-grid">
                <form
                  onSubmit={(event) => void handleSubmitFeedback(event)}
                  className="feedback-form wi-dash-feedback-form"
                >
                  <label>
                    Reason
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
                      <option value="validated">Validated</option>
                      <option value="flagged">Flagged</option>
                      <option value="needs_review">Needs review</option>
                    </select>
                  </label>
                  <label>
                    Notes
                    <textarea
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      rows={2}
                      placeholder="Optional note…"
                    />
                  </label>
                  <button type="submit" disabled={feedbackSubmitting}>
                    {feedbackSubmitting ? "Saving…" : "Save note"}
                  </button>
                  {feedbackSuccess && <p className="wi-feedback-success">{feedbackSuccess}</p>}
                </form>
                <ul className="wi-feedback-list">
                  {feedback.slice(0, 4).map((item) => (
                    <li key={item.id} className="wi-feedback-item">
                      <div className="wi-feedback-item-top">
                        <strong>{formatReason(item.reason_category)}</strong>
                        <span className={`wi-feedback-verdict wi-feedback-verdict--${item.verdict}`}>
                          {item.verdict.replace(/_/g, " ")}
                        </span>
                      </div>
                      {item.notes && <p className="wi-feedback-notes">{item.notes}</p>}
                    </li>
                  ))}
                  {feedback.length === 0 && (
                    <li className="muted">No PM notes yet.</li>
                  )}
                </ul>
              </div>
            </details>
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
