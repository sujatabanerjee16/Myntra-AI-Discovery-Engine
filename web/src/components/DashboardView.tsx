import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  age_25_35: 21,
};

const AGE_FOCUS: Record<string, string> = {
  age_18_24: "Leads on photos + occasion / forgetting",
  age_25_35: "Leads on price-too-high + fit",
};

const SHARED_PAINS = [
  { id: "price", label: "Price / sale" },
  { id: "fit", label: "Fit / size" },
  { id: "proof", label: "Proof / photos" },
  { id: "timing", label: "Timing / forget" },
] as const;
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

function confidenceTier(confidence: number | null): "high" | "medium" | "low" {
  if (confidence === null) return "low";
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

function confidencePillText(confidence: number | null): string {
  if (confidence === null) return "No score";
  return `${Math.round(confidence * 100)}%`;
}

export default function DashboardView({ filters, onFiltersChange, sidebar, onSidebarChange, onAskQuestion, view = "dashboard" }: Props) {
  const { intentType, sources, confidenceMin, platforms } = sidebar;
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

  const [appliedConfidence, setAppliedConfidence] = useState(confidenceMin);
  const confidenceRef = useRef(appliedConfidence);
  confidenceRef.current = appliedConfidence;
  const skipConfidenceReload = useRef(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedConfidence(confidenceMin), 180);
    return () => window.clearTimeout(timer);
  }, [confidenceMin]);

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
        getFilters().catch((err) => {
          setError(String(err));
          return null;
        }),
        getRankedReasons(filters, {
          minConfidence: confidenceRef.current,
          sources,
          platforms,
          intentType,
        }).catch((err) => {
          setError(String(err));
          return null;
        }),
        getConversionMetric().catch(() => null),
        listInsightFeedback().catch(() => ({ total: 0, feedback: [] as InsightFeedbackRecord[] })),
        getCompetitiveAnalysis().catch(() => null),
        getComparisons({ ...filters, segment: "" }).catch(() => null),
        getSurveyHabits(filters.segment || undefined).catch(() => null),
        getCorpusStats().catch(() => null),
      ]);
      if (filterOptions) {
        setOptions(filterOptions);
        setReasonCategory((current) => {
          const cats = filterOptions.reason_categories ?? [];
          if (cats.length && !cats.includes(current)) return cats[0];
          return current;
        });
      }
      setReasons(reasonData ?? { run_version: null, reasons: [], scope_note: null });
      setConversion(conversionData);
      setFeedback(feedbackData.feedback);
      setCompetitive(competitiveData);
      setComparisons(comparisonData);
      setSurveyHabits(habitsData);
      setCorpusStats(scrapeData);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [filters, sources, platforms, intentType]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (skipConfidenceReload.current) {
      skipConfidenceReload.current = false;
      return;
    }
    let cancelled = false;
    setLoading(true);
    void getRankedReasons(filters, {
      minConfidence: appliedConfidence,
      sources,
      platforms,
      intentType,
    })
      .then((reasonData) => {
        if (!cancelled) {
          setReasons(reasonData);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [appliedConfidence, filters, sources, platforms, intentType]);

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

  const filteredReasons = useMemo(() => {
    return (reasons?.reasons ?? []).slice().sort((a, b) => b.evidence_volume - a.evidence_volume);
  }, [reasons]);

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

  const visibleCorpus = useMemo(() => {
    if (!corpusStats) return null;
    const selected = new Set(sources);
    const activeRows = corpusStats.by_source.filter((row) => selected.has(row.source as SourceId));
    const documents = activeRows.reduce((sum, row) => sum + row.documents, 0);
    const chunks = activeRows.reduce((sum, row) => sum + row.chunks, 0);
    return { documents, chunks, by_source: corpusStats.by_source };
  }, [corpusStats, sources]);

  const topFriction =
    reasonBars.find((item) => item.reason_category !== "passive_bookmarking") ?? reasonBars[0];
  // Seed file data/seeds/internal_wishlist_events.json is 16 rows (10 wishlist users).
  // Do not show that demo cohort as a live conversion rate.
  const conversionReady =
    conversion !== null && conversion.wishlist_users > 16 && conversion.wishlist_users > 0;
  const wishlistRate = conversionReady
    ? `${(conversion!.conversion_rate * 100).toFixed(1)}%`
    : surveyHabits
      ? `${surveyHabits.respondents} people surveyed`
      : "No rate";
  const excerptScopeNote = [reasons?.scope_note].filter(Boolean).join(" · ");

  const excerptFilterLabel = [
    filters.segment ? formatReason(filters.segment) : null,
    filters.category ? formatReason(filters.category) : null,
    intentType === "high" ? "High intent" : null,
    intentType === "low" ? "Low intent" : null,
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
        .slice(0, 3);
      const excerptTotal = rows.reduce((sum, row) => sum + row.evidence_volume, 0);
      const fromApi = Number(respondents[segment] ?? 0);
      return {
        segment,
        label: formatReason(segment),
        respondents: fromApi || (rows.length ? AGE_RESPONDENT_FALLBACK[segment] : 0),
        excerptTotal,
        reasons: rows,
        focus: AGE_FOCUS[segment] ?? "",
      };
    });
  }, [comparisons]);

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
    filters.price_band ? formatReason(filters.price_band) : "All prices",
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
      platforms: ["myntra", "nykaa", "ajio", "other"],
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
          <span className="wi-dash-label">Price talk</span>
          <div className="wi-dash-pills">
            <button
              type="button"
              className={`wi-dash-pill ${filters.price_band === "" ? "active" : ""}`}
              onClick={() => onFiltersChange({ ...filters, price_band: "" })}
            >
              All
            </button>
            {(options?.price_bands?.length
              ? options.price_bands
              : ["budget", "premium", "sale_waiting"]
            ).map((value) => (
              <button
                key={value}
                type="button"
                className={`wi-dash-pill ${filters.price_band === value ? "active" : ""}`}
                onClick={() =>
                  onFiltersChange({
                    ...filters,
                    price_band: filters.price_band === value ? "" : value,
                  })
                }
              >
                {formatReason(value)}
              </button>
            ))}
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
          <p className="wi-dash-filter-hint">
            Keeps excerpts at or above this score, then re-ranks. Most sit at 45–63%. Above 65% the list shrinks; above ~80% it can empty.
          </p>
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

            {visibleCorpus && (
              <section className="wi-scrape-panel" aria-label="Scraped corpus volume by source">
                <div className="wi-scrape-totals">
                  <p className="wi-scrape-kicker">Corpus</p>
                  <p className="wi-scrape-hero">{visibleCorpus.documents.toLocaleString()}</p>
                  <p className="wi-scrape-hero-label">
                    {sources.length < 6 ? "Posts in selected sources" : "Posts collected"}
                  </p>
                  <p className="wi-scrape-split-note">
                    {evidenceTotal.toLocaleString()} excerpts match the left filters
                    {visibleCorpus.chunks > visibleCorpus.documents
                      ? ` · ${visibleCorpus.chunks.toLocaleString()} text pieces in those posts`
                      : ""}
                    .
                  </p>
                </div>
                <ul className="wi-scrape-sources">
                  {visibleCorpus.by_source.map((row) => {
                    const active = sources.includes(row.source as SourceId);
                    const share =
                      active && visibleCorpus.documents
                        ? Math.round((row.documents / visibleCorpus.documents) * 100)
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
                          {book.file.replace(/\.xlsx$/i, "")} · {book.n} people
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
                  {intentSum ? (
                    <>
                      <div className="wi-intent-pair">
                        <span>Buy soon</span>
                        <span>Save later</span>
                        <strong>{activePct}%</strong>
                        <strong>{passivePct}%</strong>
                      </div>
                      {excerptScopeNote ? <p className="wi-kpi-sub">{excerptScopeNote}</p> : null}
                    </>
                  ) : (
                    <p className="wi-kpi-sub">
                      {excerptFilterLabel
                        ? `No tagged excerpts for ${excerptFilterLabel}`
                        : "No tagged excerpts in this filter"}
                    </p>
                  )}
                </article>
                <article className="wi-kpi-card">
                  <h3>Evidence excerpts</h3>
                  <p className="wi-kpi-value">{evidenceTotal.toLocaleString()}</p>
                  <p className="wi-kpi-sub">
                  {evidenceTotal
                    ? excerptScopeNote || "Chunks in this filter, not people"
                    : excerptFilterLabel
                      ? `No tagged chunks for ${excerptFilterLabel}`
                      : "Chunks in this filter, not people"}
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
                <h2>18–24 vs 25–35</h2>
                <p className="wi-age-lead">Same four pains. Different order.</p>
              </div>

              <ul className="wi-shared-pains">
                {SHARED_PAINS.map((pain) => (
                  <li key={pain.id}>{pain.label}</li>
                ))}
              </ul>
              <p className="wi-age-takeaway">
                v1 opportunity: real photos + one price-drop reminder
              </p>

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
                          {cohort.respondents ? `${cohort.respondents} people` : "No survey"}
                        </span>
                      </header>
                      {cohort.focus && <p className="wi-age-focus">{cohort.focus}</p>}
                      <div className="wi-age-reasons">
                        {cohort.reasons.length === 0 ? (
                          <p className="muted">No reasons yet</p>
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
                        {selected ? "Clear filter" : `View ${cohort.label}`}
                      </button>
                    </article>
                  );
                })}
              </div>
            </section>

            <section className="wi-dash-card">
              <h2>Why wishlists do not convert</h2>
              <p className="wi-kpi-sub" style={{ marginTop: "-0.55rem", marginBottom: "0.9rem" }}>
                Top reasons from excerpts at ≥{Math.round(appliedConfidence * 100)}% confidence
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
                      {confidencePillText(item.confidence)}
                    </span>
                  </div>
                ))}
                {reasonBars.length === 0 && (
                  <p className="wi-reason-empty">
                    Nothing in the current filters is at ≥{Math.round(appliedConfidence * 100)}%
                    confidence. Lower the slider or clear a source — most scores sit at 45–63%.
                  </p>
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
