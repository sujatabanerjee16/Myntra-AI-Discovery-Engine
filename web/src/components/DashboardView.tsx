import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getComparisons,
  getCompetitiveAnalysis,
  getConversionMetric,
  getCorpusStats,
  getDashboardBootstrap,
  getFilters,
  getRankedReasons,
  getSurveyHabits,
  listInsightFeedback,
  submitInsightFeedback,
} from "../api";
import bundledBootstrap from "../data/dashboard-bootstrap.json";
import { COMPETITIVE_PLATFORMS, PLATFORM_META } from "../types";
import type {
  ComparisonResponse,
  CompetitiveAnalysisResponse,
  ConversionMetricResponse,
  CorpusScrapeStats,
  DashboardBootstrap,
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
import CompetitiveAnalysisPanel from "./CompetitiveAnalysisPanel";
import { formatReason } from "./ConfidenceBadge";
import QuestionsView from "./QuestionsView";

const AGE_SEGMENTS = ["age_18_24", "age_25_35"] as const;

const WORKBOOK_LABELS: Record<string, string> = {
  "myntra-wishlist": "Myntra Wishlist",
  "your-wishlist-habits-responses": "Wishlist Habits",
};

/** Last-resort survey sizes when the API omits respondent_counts. */
const AGE_RESPONDENT_FALLBACK: Record<(typeof AGE_SEGMENTS)[number], number> = {
  age_18_24: 27,
  age_25_35: 15,
};

const SNAPSHOT = bundledBootstrap as DashboardBootstrap;

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
];

export default function DashboardView({ filters, onFiltersChange, sidebar, onSidebarChange, onAskQuestion, view = "dashboard" }: Props) {
  const { intentType, sources, confidenceMin, platforms } = sidebar;
  const setIntentType = (value: IntentType) => onSidebarChange({ ...sidebar, intentType: value });
  const setConfidenceMin = (value: number) => onSidebarChange({ ...sidebar, confidenceMin: value });

  const [options, setOptions] = useState<DashboardFilters | null>(SNAPSHOT.filters);
  const [reasons, setReasons] = useState<ReasonRankResponse | null>(SNAPSHOT.reasons);
  const [conversion, setConversion] = useState<ConversionMetricResponse | null>(SNAPSHOT.conversion);
  const [competitive, setCompetitive] = useState<CompetitiveAnalysisResponse | null>(SNAPSHOT.competitive);
  const [comparisons, setComparisons] = useState<ComparisonResponse | null>(SNAPSHOT.comparisons);
  const [surveyHabits, setSurveyHabits] = useState<SurveyHabitsResponse | null>(SNAPSHOT.survey_habits);
  const [corpusStats, setCorpusStats] = useState<CorpusScrapeStats | null>(SNAPSHOT.corpus_stats);
  const [feedback, setFeedback] = useState<InsightFeedbackRecord[]>(SNAPSHOT.feedback?.feedback ?? []);
  const [loading, setLoading] = useState(false);
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
  const skipFirstNetworkLoad = useRef(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedConfidence(confidenceMin), 180);
    return () => window.clearTimeout(timer);
  }, [confidenceMin]);

  const applyBootstrap = useCallback((snap: DashboardBootstrap) => {
    if (snap.filters) {
      setOptions(snap.filters);
      setReasonCategory((current) => {
        const cats = snap.filters.reason_categories ?? [];
        if (cats.length && !cats.includes(current)) return cats[0];
        return current;
      });
    }
    if (snap.reasons) setReasons(snap.reasons);
    if (snap.conversion !== undefined) setConversion(snap.conversion);
    if (snap.feedback?.feedback) setFeedback(snap.feedback.feedback);
    if (snap.competitive !== undefined) setCompetitive(snap.competitive);
    if (snap.comparisons !== undefined) setComparisons(snap.comparisons);
    if (snap.survey_habits !== undefined) setSurveyHabits(snap.survey_habits);
    if (snap.corpus_stats !== undefined) setCorpusStats(snap.corpus_stats);
  }, []);

  const fetchLiveDashboard = useCallback(async () => {
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
  }, [filters, sources, intentType]);

  const loadDashboard = useCallback(async () => {
    setError(null);
    if (skipFirstNetworkLoad.current) {
      skipFirstNetworkLoad.current = false;
      void getDashboardBootstrap()
        .then((live) => applyBootstrap(live))
        .catch(() => {
          /* Bundled snapshot is already on screen. */
        });
      return;
    }

    setLoading(true);
    try {
      await fetchLiveDashboard();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [applyBootstrap, fetchLiveDashboard]);

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
  }, [appliedConfidence, filters, sources, intentType]);

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

  const reasonBars = useMemo(() => {
    const top = filteredReasons.slice(0, 5);
    const shownVolume = top.reduce((sum, item) => sum + item.evidence_volume, 0) || 1;
    const raw = top.map((item) => (item.evidence_volume / shownVolume) * 100);
    const floored = raw.map((value) => Math.floor(value));
    let leftover = 100 - floored.reduce((sum, value) => sum + value, 0);
    const byFraction = raw
      .map((value, index) => ({ index, frac: value - Math.floor(value) }))
      .sort((a, b) => b.frac - a.frac);
    const pcts = [...floored];
    for (let i = 0; i < leftover && i < byFraction.length; i += 1) {
      pcts[byFraction[i].index] += 1;
    }
    return top.map((item, index) => ({
      ...item,
      pct: top.length ? pcts[index] : 0,
      label: formatReason(item.reason_category),
    }));
  }, [filteredReasons]);

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
  const intentThin = intentSum > 0 && intentSum < 10;
  const intentTautology =
    intentType === "high" || intentType === "low" || filters.price_band === "sale_waiting";

  const evidenceTotal = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0),
    [filteredReasons],
  );

  const visibleCorpus = useMemo(() => {
    if (!corpusStats) return null;
    const selected = new Set(sources);
    const countBySource = new Map(
      corpusStats.by_source.map((row) => [row.source, row] as const),
    );
    const scrapedRows = SOURCES.filter((item) => selected.has(item.id)).map((item) => {
      const row = countBySource.get(item.id);
      return {
        source: item.id,
        label: item.label,
        documents: row?.documents ?? 0,
        chunks: row?.chunks ?? 0,
      };
    });
    const scrapedDocuments = scrapedRows.reduce((sum, row) => sum + row.documents, 0);
    const surveyRespondents = corpusStats.survey_respondents ?? 0;
    const surveyOpenText = corpusStats.survey_open_text ?? 0;
    const surveyInterviews = corpusStats.survey_interviews ?? 0;
    return {
      scrapedDocuments,
      scrapedLabels: scrapedRows.map((row) => row.label).join(", ") || "No sources selected",
      surveyRespondents,
      surveyOpenText,
      surveyInterviews,
      surveyByWorkbook: corpusStats.survey_by_workbook ?? [],
      scrapedRows,
    };
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
    : "Excel survey — category and price filters do not change this";

  const intentNote = !intentSum
    ? null
    : intentType === "high"
      ? "High filter is on, so every comment here is High. Not a purchase rate."
      : intentType === "low"
        ? "Low filter is on, so every comment here is Low. Not a purchase rate."
        : filters.price_band === "sale_waiting"
          ? "Sale waiting is tagged High. Not people who bought."
          : "All comments in this filter, split into High and Low. Not a purchase rate.";
  const nonConversionRate = conversionReady
    ? `${(conversion!.non_conversion_rate * 100).toFixed(1)}%`
    : null;

  const ageComparison = useMemo(() => {
    const items = comparisons?.items ?? [];
    const respondents = comparisons?.respondent_counts ?? {};
    return AGE_SEGMENTS.map((segment) => {
      const allRows = items
        .filter((item) => item.dimension === segment)
        .sort((a, b) => b.evidence_volume - a.evidence_volume);
      const rows = allRows.slice(0, 5);
      const excerptTotal = allRows.reduce((sum, row) => sum + row.evidence_volume, 0);
      const fromApi = Number(respondents[segment] ?? 0);
      const origin = comparisons?.age_origin_counts?.[segment];
      return {
        segment,
        label: formatReason(segment),
        respondents: fromApi || (rows.length ? AGE_RESPONDENT_FALLBACK[segment] : 0),
        surveyCount: origin?.survey ?? fromApi,
        playStoreCount: origin?.play_store ?? 0,
        otherScrapeCount: origin?.other_scrape ?? 0,
        excerptTotal,
        reasons: rows,
      };
    });
  }, [comparisons]);

  const agePainSplit = useMemo(() => {
    const younger = new Set(
      (ageComparison.find((cohort) => cohort.segment === "age_18_24")?.reasons ?? []).map(
        (row) => row.reason_category,
      ),
    );
    const older = new Set(
      (ageComparison.find((cohort) => cohort.segment === "age_25_35")?.reasons ?? []).map(
        (row) => row.reason_category,
      ),
    );
    const shared = [...younger].filter((reason) => older.has(reason));
    const youngerOnly = [...younger].filter((reason) => !older.has(reason));
    const olderOnly = [...older].filter((reason) => !younger.has(reason));
    const headline = "Shared pains, then what each age adds";
    const youngCount = ageComparison.find((cohort) => cohort.segment === "age_18_24")?.surveyCount ?? 0;
    const olderCount = ageComparison.find((cohort) => cohort.segment === "age_25_35")?.surveyCount ?? 0;
    const surveyPeople =
      surveyHabits?.respondents || visibleCorpus?.surveyRespondents || youngCount + olderCount;
    const playStorePeople = sources.includes("play_store")
      ? ageComparison.reduce((sum, cohort) => sum + (cohort.playStoreCount || 0), 0)
      : 0;
    const otherPeople = sources.some((id) => id !== "play_store")
      ? ageComparison.reduce((sum, cohort) => sum + (cohort.otherScrapeCount || 0), 0)
      : 0;
    const ageSplit =
      youngCount || olderCount ? ` ${youngCount} are 18–24, ${olderCount} are 25–35.` : "";
    const sourceNote =
      playStorePeople || otherPeople
        ? `${surveyPeople} survey people.` +
          (playStorePeople ? ` ${playStorePeople} Play Store.` : "") +
          (otherPeople ? ` ${otherPeople} other scrapes.` : "") +
          ageSplit
        : `From the same ${surveyPeople} survey people.${ageSplit}`;
    return { shared, youngerOnly, olderOnly, headline, sourceNote };
  }, [ageComparison, surveyHabits, visibleCorpus, sources]);

  const categoryOptions = options?.categories?.length
    ? options.categories
    : ["clothing", "beauty", "footwear", "accessories"];

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
    intentType === "high" ? "High intent" : intentType === "low" ? "Low intent" : "All intents",
    view === "competitive" ? null : `${sources.length} source${sources.length === 1 ? "" : "s"}`,
    `≥${Math.round(confidenceMin * 100)}% conf.`,
  ]
    .filter(Boolean)
    .join(" · ");

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
      sources: ["play_store", "youtube", "reddit", "product_review", "social"],
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
            <button
              type="button"
              className="wi-dash-clear"
              onClick={
                view === "competitive"
                  ? () => onSidebarChange({ ...sidebar, platforms: [...COMPETITIVE_PLATFORMS] })
                  : clearSidebarFilters
              }
            >
              Reset
            </button>
          </div>
          {view !== "competitive" && <p className="wi-dash-active-summary">{activeFilterSummary}</p>}
          {view === "competitive" && (
            <p className="wi-dash-filter-hint">
              Compare named competitors. Dashboard filters (age, category, source) do not apply here.
            </p>
          )}
        </div>

        {view !== "competitive" && (
          <>
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
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                category: e.target.value.trim().toLowerCase().replace(/[\s-]+/g, "_"),
              })
            }
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
          <span className="wi-dash-label">Intent</span>
          <div className="wi-dash-pills">
            {(
              [
                { id: "medium", label: "All intents" },
                { id: "high", label: "High" },
                { id: "low", label: "Low" },
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
            Drops weaker comments. Counts change first; above ~80% the list can empty.
          </p>
        </div>
          </>
        )}

        {view === "competitive" && (
        <div className="wi-dash-filter">
          <span className="wi-dash-label">Platform</span>
          <div className="wi-dash-platforms">
            {PLATFORM_META.filter((item) => COMPETITIVE_PLATFORMS.includes(item.id)).map((item) => {
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
        )}
      </aside>

      <div className="wi-dash-content">
        {error && <div className="error-banner">{error}</div>}
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
              <section className="wi-scrape-panel" aria-label="Survey vs scraped corpus">
                <div className="wi-scrape-family">
                  <p className="wi-scrape-kicker">Surveys</p>
                  <p className="wi-scrape-hero">{visibleCorpus.surveyRespondents.toLocaleString()}</p>
                  <p className="wi-scrape-hero-label">Unique Excel respondents</p>
                  <ul className="wi-scrape-sources">
                    {visibleCorpus.surveyByWorkbook.map((row) => (
                      <li key={row.workbook} className="wi-scrape-source">
                        <div className="wi-scrape-source-top">
                          <span>{WORKBOOK_LABELS[row.workbook] ?? formatReason(row.workbook)}</span>
                          <strong>{row.respondents.toLocaleString()}</strong>
                        </div>
                      </li>
                    ))}
                    {visibleCorpus.surveyOpenText > 0 && (
                      <li className="wi-scrape-source">
                        <div className="wi-scrape-source-top">
                          <span>Open-text extras (same people)</span>
                          <strong>{visibleCorpus.surveyOpenText.toLocaleString()}</strong>
                        </div>
                      </li>
                    )}
                    {visibleCorpus.surveyInterviews > 0 && (
                      <li className="wi-scrape-source">
                        <div className="wi-scrape-source-top">
                          <span>Interviews</span>
                          <strong>{visibleCorpus.surveyInterviews.toLocaleString()}</strong>
                        </div>
                      </li>
                    )}
                  </ul>
                </div>
                <div className="wi-scrape-family">
                  <p className="wi-scrape-kicker">Scraped</p>
                  <p className="wi-scrape-hero">{visibleCorpus.scrapedDocuments.toLocaleString()}</p>
                  <p className="wi-scrape-hero-label">{visibleCorpus.scrapedLabels}</p>
                  <ul className="wi-scrape-sources">
                    {visibleCorpus.scrapedRows.map((row) => {
                      const share = visibleCorpus.scrapedDocuments
                        ? Math.round((row.documents / visibleCorpus.scrapedDocuments) * 100)
                        : 0;
                      return (
                        <li key={row.source} className="wi-scrape-source">
                          <div className="wi-scrape-source-top">
                            <span>{row.label}</span>
                            <strong>
                              {row.documents.toLocaleString()}
                              <em>{share}%</em>
                            </strong>
                          </div>
                          <div className="wi-scrape-source-track" aria-hidden="true">
                            <div
                              className="wi-scrape-source-fill"
                              style={{ width: `${share}%` }}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
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
                  <h3>
                    {intentType === "high"
                      ? "High comments"
                      : intentType === "low"
                        ? "Low comments"
                        : filters.price_band === "sale_waiting"
                          ? "Sale-waiting comments"
                          : "High vs Low"}
                  </h3>
                  {intentSum ? (
                    intentTautology ? (
                      <>
                        <p className="wi-kpi-value">{intentSum.toLocaleString()}</p>
                        <p className="wi-kpi-sub">{intentNote}</p>
                      </>
                    ) : (
                    <>
                      <div className="wi-intent-pair">
                        <span>High</span>
                        <span>Low</span>
                        <strong>
                          {intentThin ? activeTotal.toLocaleString() : `${activePct}%`}
                        </strong>
                        <strong>
                          {intentThin ? passiveTotal.toLocaleString() : `${passivePct}%`}
                        </strong>
                        {!intentThin && (
                          <>
                            <span className="wi-intent-count">{activeTotal.toLocaleString()} comments</span>
                            <span className="wi-intent-count">{passiveTotal.toLocaleString()} comments</span>
                          </>
                        )}
                      </div>
                      <p className="wi-kpi-sub">{intentNote}</p>
                    </>
                    )
                  ) : (
                    <p className="wi-kpi-sub">
                      {excerptFilterLabel
                        ? `No comments for ${excerptFilterLabel}`
                        : "No comments in this filter"}
                    </p>
                  )}
                </article>
                <article className="wi-kpi-card">
                  <h3>Comments</h3>
                  <p className="wi-kpi-value">{evidenceTotal.toLocaleString()}</p>
                  <p className="wi-kpi-sub">
                  {evidenceTotal
                    ? excerptScopeNote || "Comments in this filter — not unique people"
                    : excerptFilterLabel
                      ? `No comments for ${excerptFilterLabel}`
                      : "Comments in this filter — not unique people"}
                </p>
                </article>
                <article className="wi-kpi-card">
                  <h3>Top Friction</h3>
                  <p className="wi-kpi-value wi-kpi-value--sm">
                    {topFriction
                      ? evidenceTotal < 10
                        ? `${topFriction.label} · ${topFriction.evidence_volume} comments`
                        : `${topFriction.label} ${topFriction.pct}%`
                      : "—"}
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
                <p className="wi-age-lead">{agePainSplit.headline}</p>
                <p className="wi-age-source-note">{agePainSplit.sourceNote}</p>
              </div>

              <div className="wi-age-pain-groups">
                {agePainSplit.shared.length > 0 && (
                  <div className="wi-age-lane wi-age-lane--shared">
                    <p className="wi-age-pain-kicker">
                      Shared
                      <span>{agePainSplit.shared.length}</span>
                    </p>
                    <ul className="wi-shared-pains">
                      {agePainSplit.shared.map((reason) => (
                        <li key={reason} className="wi-pain-name">
                          {formatReason(reason)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {agePainSplit.youngerOnly.length > 0 && (
                  <div className="wi-age-lane wi-age-lane--young">
                    <p className="wi-age-pain-kicker">
                      18–24 also
                      <span>{agePainSplit.youngerOnly.length}</span>
                    </p>
                    <ul className="wi-shared-pains">
                      {agePainSplit.youngerOnly.map((reason) => (
                        <li key={reason} className="wi-pain-name">
                          {formatReason(reason)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {agePainSplit.olderOnly.length > 0 && (
                  <div className="wi-age-lane wi-age-lane--older">
                    <p className="wi-age-pain-kicker">
                      25–35 also
                      <span>{agePainSplit.olderOnly.length}</span>
                    </p>
                    <ul className="wi-shared-pains">
                      {agePainSplit.olderOnly.map((reason) => (
                        <li key={reason} className="wi-pain-name">
                          {formatReason(reason)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
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
                          {cohort.surveyCount > 0 && <span>{cohort.surveyCount} survey</span>}
                          {cohort.playStoreCount > 0 && sources.includes("play_store") && (
                            <span>{cohort.playStoreCount} Play Store</span>
                          )}
                          {cohort.otherScrapeCount > 0 &&
                            sources.some((id) => id !== "play_store") && (
                            <span>{cohort.otherScrapeCount} other</span>
                          )}
                        </span>
                      </header>
                      <div className="wi-age-reasons">
                        {cohort.reasons.length === 0 ? (
                          <p className="muted">No reasons yet</p>
                        ) : (
                          cohort.reasons.map((row) => (
                            <div key={row.reason_category} className="wi-age-reason-row">
                              <span className="wi-pain-name">{formatReason(row.reason_category)}</span>
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
                        {selected ? "Clear filter" : "Use this filter"}
                      </button>
                    </article>
                  );
                })}
              </div>
            </section>

            <section className="wi-dash-card">
              <h2>Why wishlists do not convert</h2>
              <p className="wi-kpi-sub" style={{ marginTop: "-0.55rem", marginBottom: "0.9rem" }}>
                {evidenceTotal.toLocaleString()} comments at ≥
                {Math.round(appliedConfidence * 100)}% confidence. Bar length is share of the
                reasons shown — the % on the right is that same share.
              </p>
              <div className="wi-reason-bars">
                {reasonBars.map((item) => (
                  <div key={item.reason_category} className="wi-reason-bar-row">
                    <span className="wi-reason-bar-label wi-pain-name">{item.label}</span>
                    <div className="wi-reason-bar-main">
                      <div className="wi-reason-bar-track">
                        <div
                          className="wi-reason-bar-fill"
                          style={{ width: `${item.pct}%` }}
                        />
                      </div>
                      <span className="wi-reason-bar-pct">
                        {item.evidence_volume.toLocaleString()} comments
                      </span>
                    </div>
                    <span
                      className="wi-share-pill"
                      title={
                        item.confidence == null
                          ? "No model confidence"
                          : `Model confidence ${Math.round(item.confidence * 100)}% (not the bar)`
                      }
                    >
                      {item.pct}%
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
                <h2>PM calibration</h2>
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
                  {feedback.map((item) => (
                    <li key={item.id} className="wi-feedback-item">
                      <div className="wi-feedback-item-top">
                        <strong className="wi-pain-name">{formatReason(item.reason_category)}</strong>
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
          <CompetitiveAnalysisPanel
            data={competitive}
            loading={loading}
            selectedPlatforms={platforms.filter((id) => COMPETITIVE_PLATFORMS.includes(id))}
          />
        )}
      </div>
    </div>
  );
}
