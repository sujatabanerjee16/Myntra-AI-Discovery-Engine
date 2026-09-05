import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getCompetitiveAnalysis,
  getCorpusStats,
  getDashboardBootstrap,
  getEvidence,
  getFilters,
  getRankedReasons,
  listInsightFeedback,
  submitInsightFeedback,
} from "../api";
import bundledBootstrap from "../data/dashboard-bootstrap.json";
import { COMPETITIVE_PLATFORMS, DEFAULT_SIDEBAR, PLATFORM_META } from "../types";
import type {
  CompetitiveAnalysisResponse,
  CorpusScrapeStats,
  DashboardBootstrap,
  DashboardFilters,
  FilterState,
  InsightFeedbackRecord,
  PlatformId,
  ReasonRankResponse,
  SidebarFilters,
  SourceId,
  VoicePreviewGroup,
} from "../types";
import CompetitiveAnalysisPanel from "./CompetitiveAnalysisPanel";
import { formatReason } from "./ConfidenceBadge";
import QuestionsView from "./QuestionsView";

const OPP_RAIL_COLORS = [
  "#e11d48",
  "#eab308",
  "#f97316",
  "#3b82f6",
  "#22d3ee",
  "#22c55e",
  "#7c3aed",
];

const VOICE_TONES: Record<string, { bg: string; ink: string; chip: string }> = {
  price_sensitivity_waiting: { bg: "#ffe4e6", ink: "#9f1239", chip: "#e11d48" },
  logistics_friction: { bg: "#fef08a", ink: "#713f12", chip: "#ca8a04" },
  fit_sizing_uncertainty: { bg: "#bfdbfe", ink: "#1e3a8a", chip: "#2563eb" },
  external_comparison: { bg: "#a5f3fc", ink: "#155e75", chip: "#0891b2" },
  timing_occasion: { bg: "#bbf7d0", ink: "#14532d", chip: "#16a34a" },
  quality_trust_doubt: { bg: "#fed7aa", ink: "#9a3412", chip: "#ea580c" },
  review_trust: { bg: "#ddd6fe", ink: "#5b21b6", chip: "#7c3aed" },
  styling_decision_uncertainty: { bg: "#fbcfe8", ink: "#9d174d", chip: "#db2777" },
};

const VOICE_TONE_FALLBACK = { bg: "#e2e8f0", ink: "#334155", chip: "#64748b" };

const SOURCE_COLORS: Record<string, string> = {
  play_store: "#fb7185",
  youtube: "#f43f5e",
  reddit: "#f97316",
  product_review: "#38bdf8",
  social: "#a78bfa",
};

const SOURCE_PLAIN: Record<string, string> = {
  play_store: "Play Store reviews",
  youtube: "YouTube comments",
  reddit: "Reddit threads",
  product_review: "Product reviews",
  social: "Social posts",
};

const SNAPSHOT = bundledBootstrap as DashboardBootstrap;

const REASON_CODES: Record<string, string> = {
  price_sensitivity_waiting: "PRI",
  logistics_friction: "LOG",
  quality_trust_doubt: "QLT",
  fit_sizing_uncertainty: "FIT",
  external_comparison: "CMP",
  timing_occasion: "TIM",
  review_trust: "PRF",
  styling_decision_uncertainty: "STY",
  passive_bookmarking: "PAS",
};

const SOURCE_TAGS: Record<string, string> = {
  play_store: "PLAY_STORE",
  youtube: "YOUTUBE",
  reddit: "REDDIT",
  product_review: "PRODUCT_REVIEW",
  social: "SOCIAL",
  research: "SURVEY",
};

function clipVoiceLine(text: string, maxLen = 140): string {
  let line = text.replace(/\s+/g, " ").trim();
  const answer = line.match(/\bA:\s*(.+)$/i);
  if (answer) line = answer[1].trim();
  line = line.replace(/^Comment on [^:]+:\s*/i, "");
  if (line.length > maxLen) {
    const clipped = line.slice(0, maxLen).replace(/\s+\S*$/, "");
    line = `${(clipped || line.slice(0, maxLen)).replace(/[.,;:]+$/, "")}…`;
  }
  return line;
}

const VOICE_EXTRA_REASONS = [
  "fit_sizing_uncertainty",
  "external_comparison",
  "timing_occasion",
] as const;

function pickVoiceReasons<T extends { reason_category: string }>(reasons: T[]): T[] {
  const selected = [...reasons.slice(0, 2)];
  const have = new Set(selected.map((item) => item.reason_category));
  for (const key of VOICE_EXTRA_REASONS) {
    if (have.has(key)) continue;
    const row = reasons.find((item) => item.reason_category === key);
    if (row) {
      selected.push(row);
      have.add(key);
    }
  }
  return selected;
}

function sourceTag(source: string): string {
  return SOURCE_TAGS[source] ?? source.replace(/[_-]+/g, "_").toUpperCase();
}

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
  const { sources, confidenceMin, platforms } = sidebar;
  const setConfidenceMin = (value: number) => onSidebarChange({ ...sidebar, confidenceMin: value });

  const [options, setOptions] = useState<DashboardFilters | null>(SNAPSHOT.filters);
  const [reasons, setReasons] = useState<ReasonRankResponse | null>(SNAPSHOT.reasons);
  const [competitive, setCompetitive] = useState<CompetitiveAnalysisResponse | null>(SNAPSHOT.competitive);
  const [corpusStats, setCorpusStats] = useState<CorpusScrapeStats | null>(SNAPSHOT.corpus_stats);
  const [feedback, setFeedback] = useState<InsightFeedbackRecord[]>(SNAPSHOT.feedback?.feedback ?? []);
  const [voicePreview, setVoicePreview] = useState<VoicePreviewGroup[]>(SNAPSHOT.voice_preview ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [reasonCategory, setReasonCategory] = useState("price_sensitivity_waiting");
  const [verdict, setVerdict] = useState("validated");
  const [notes, setNotes] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  const [appliedConfidence, setAppliedConfidence] = useState(confidenceMin);
  const confidenceRef = useRef(appliedConfidence);
  confidenceRef.current = appliedConfidence;
  const skipFirstNetworkLoad = useRef(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setAppliedConfidence(confidenceMin), 80);
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
    // Don't reset the matrix if the PM already moved the confidence slider.
    if (snap.reasons && confidenceRef.current === DEFAULT_SIDEBAR.confidenceMin) {
      setReasons(snap.reasons);
    }
    if (snap.feedback?.feedback) setFeedback(snap.feedback.feedback);
    if (snap.competitive) setCompetitive(snap.competitive);
    if (snap.corpus_stats?.by_source?.length) setCorpusStats(snap.corpus_stats);
    if (snap.voice_preview?.length) setVoicePreview(snap.voice_preview);
  }, []);

  const fetchLiveDashboard = useCallback(async () => {
    const [
      filterOptions,
      reasonData,
      feedbackData,
      competitiveData,
      scrapeData,
    ] = await Promise.all([
      getFilters().catch(() => null),
      getRankedReasons({ ...filters, segment: "", price_band: "" }, {
        minConfidence: confidenceRef.current,
        sources,
        intentType: "medium",
      }).catch(() => null),
      listInsightFeedback().catch(() => null),
      getCompetitiveAnalysis().catch(() => null),
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
    if (reasonData) setReasons(reasonData);
    if (feedbackData?.feedback) setFeedback(feedbackData.feedback);
    if (competitiveData) setCompetitive(competitiveData);
    if (scrapeData?.by_source?.length) setCorpusStats(scrapeData);
  }, [filters, sources]);

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
    } catch {
      /* Keep the snapshot if the live API is down. */
    } finally {
      setLoading(false);
    }
  }, [applyBootstrap, fetchLiveDashboard]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getRankedReasons({ ...filters, segment: "", price_band: "" }, {
      minConfidence: appliedConfidence,
      sources,
      intentType: "medium",
    })
      .then((reasonData) => {
        if (!cancelled) {
          setReasons(reasonData);
          setError(null);
        }
      })
      .catch(() => {
        /* Client-side confidence filter still updates the matrix. */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [appliedConfidence, filters, sources]);

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
    return (reasons?.reasons ?? [])
      .filter((item) => item.confidence == null || item.confidence + 1e-9 >= confidenceMin)
      .sort((a, b) => b.evidence_volume - a.evidence_volume);
  }, [reasons, confidenceMin]);

  const reasonBars = useMemo(() => {
    const top = filteredReasons.slice(0, 7);
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

  const evidenceTotal = useMemo(
    () => filteredReasons.reduce((sum, item) => sum + item.evidence_volume, 0),
    [filteredReasons],
  );

  const voiceReasons = useMemo(() => pickVoiceReasons(filteredReasons), [filteredReasons]);
  const voiceReasonKey = voiceReasons.map((item) => item.reason_category).join("|");

  useEffect(() => {
    if (voiceReasons.length === 0) return;
    let cancelled = false;
    void Promise.all(
      voiceReasons.map(async (item) => {
        const summary = await getEvidence(item.reason_category, { ...filters, segment: "", price_band: "" });
        const lines: VoicePreviewGroup["lines"] = [];
        const seen = new Set<string>();
        for (const excerpt of summary.excerpts) {
          if (excerpt.source === "research") continue;
          const text = clipVoiceLine(excerpt.text);
          const key = text.toLowerCase();
          if (text.length < 24 || seen.has(key)) continue;
          seen.add(key);
          lines.push({ text, source: excerpt.source });
          if (lines.length >= 1) break;
        }
        return {
          reason_category: item.reason_category,
          code: REASON_CODES[item.reason_category] ?? item.reason_category.slice(0, 3).toUpperCase(),
          evidence_volume: item.evidence_volume,
          lines,
        } satisfies VoicePreviewGroup;
      }),
    )
      .then((groups) => {
        if (!cancelled) setVoicePreview(groups.filter((group) => group.lines.length > 0));
      })
      .catch(() => {
        /* Keep the bundled preview. */
      });
    return () => {
      cancelled = true;
    };
  }, [voiceReasonKey, filters, voiceReasons]);

  const visibleCorpus = useMemo(() => {
    const stats = corpusStats ?? SNAPSHOT.corpus_stats;
    if (!stats) return null;
    const selected = new Set(sources);
    const countBySource = new Map(
      stats.by_source.map((row) => [row.source, row] as const),
    );
    const scrapedRows = SOURCES.filter((item) => selected.has(item.id))
      .map((item) => {
        const row = countBySource.get(item.id);
        return {
          source: item.id,
          label: SOURCE_PLAIN[item.id] ?? item.label,
          documents: row?.documents ?? 0,
        };
      })
      .sort((a, b) => b.documents - a.documents);
    const scrapedDocuments = scrapedRows.reduce((sum, row) => sum + row.documents, 0);
    const ranked = scrapedRows.filter((row) => row.documents > 0);
    const topShare = scrapedDocuments && ranked[0]
      ? Math.round((ranked[0].documents / scrapedDocuments) * 100)
      : 0;
    let scrapedMix = "Public reviews, videos, and posts.";
    if (ranked[0] && ranked[1]) {
      scrapedMix = `${topShare}% ${ranked[0].label}, then ${ranked[1].label}.`;
    } else if (ranked[0]) {
      scrapedMix = `All from ${ranked[0].label}.`;
    } else if (scrapedRows.length) {
      scrapedMix = "Turn a source back on in the filter rail to see counts.";
    }
    return {
      scrapedDocuments,
      scrapedMix,
      scrapedRows,
    };
  }, [corpusStats, sources]);

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
    filters.category ? formatReason(filters.category) : "All categories",
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
    if (filters.segment) {
      onFiltersChange({ ...filters, segment: "" });
    }
  }, [filters, onFiltersChange]);

  const pmCounts = useMemo(() => {
    const counts = { validated: 0, flagged: 0, needs_review: 0, total: feedback.length };
    for (const item of feedback) {
      if (item.verdict === "validated") counts.validated += 1;
      else if (item.verdict === "flagged") counts.flagged += 1;
      else if (item.verdict === "needs_review") counts.needs_review += 1;
    }
    return counts;
  }, [feedback]);

  const pmNoteCount = feedback.length
    ? `${feedback.length} note${feedback.length === 1 ? "" : "s"}`
    : "No notes yet";

  const formatFeedbackWhen = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return iso.slice(0, 10);
    }
  };

  const pmCalibrationBody = (
    <>
      <p className="wi-kpi-sub">
        Internal PM loop — not scraped user data. Validate a reason when public evidence looks
        solid, flag when it looks wrong, or mark needs review. Each verdict nudges confidence for
        that reason.
      </p>

      <div className="wi-pm-impact" aria-label="How verdicts change confidence">
        <div className="wi-pm-impact-card wi-pm-impact-card--validated">
          <strong>Validated</strong>
          <span>+0.05 confidence</span>
          <em>Keep — evidence looks right</em>
        </div>
        <div className="wi-pm-impact-card wi-pm-impact-card--flagged">
          <strong>Flagged</strong>
          <span>−0.12 confidence</span>
          <em>Down-rank — looks wrong or thin</em>
        </div>
        <div className="wi-pm-impact-card wi-pm-impact-card--review">
          <strong>Needs review</strong>
          <span>−0.03 confidence</span>
          <em>Park — more interviews / checks</em>
        </div>
      </div>

      <div className="wi-pm-summary" aria-label="Calibration summary">
        <span>
          <strong>{pmCounts.total}</strong> total
        </span>
        <span className="wi-pm-summary--validated">
          <strong>{pmCounts.validated}</strong> validated
        </span>
        <span className="wi-pm-summary--flagged">
          <strong>{pmCounts.flagged}</strong> flagged
        </span>
        <span className="wi-pm-summary--review">
          <strong>{pmCounts.needs_review}</strong> needs review
        </span>
      </div>

      <div className="wi-pm-calibrate-grid">
        <form
          onSubmit={(event) => void handleSubmitFeedback(event)}
          className="feedback-form wi-dash-feedback-form"
        >
          <p className="wi-pm-form-title">Add a calibration note</p>
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
              <option value="validated">Validated (+0.05)</option>
              <option value="flagged">Flagged (−0.12)</option>
              <option value="needs_review">Needs review (−0.03)</option>
            </select>
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={4}
              placeholder="Why this verdict? e.g. Beauty barrier looks right — flag for interview follow-up."
            />
          </label>
          <button type="submit" disabled={feedbackSubmitting}>
            {feedbackSubmitting ? "Saving…" : "Save calibration note"}
          </button>
          {feedbackSuccess && <p className="wi-feedback-success">{feedbackSuccess}</p>}
        </form>

        <div className="wi-pm-history">
          <div className="wi-pm-history-head">
            <p className="wi-pm-form-title">Recent notes</p>
            <span>{pmNoteCount}</span>
          </div>
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
                <p className="wi-feedback-item-meta">
                  {item.reviewer || "pm"}
                  {" · "}
                  {formatFeedbackWhen(item.created_at)}
                  {item.adjusted_confidence != null && (
                    <>
                      {" · "}
                      confidence → {item.adjusted_confidence.toFixed(2)}
                    </>
                  )}
                </p>
              </li>
            ))}
            {feedback.length === 0 && (
              <li className="muted">No PM notes yet — validate or flag a reason to start the loop.</li>
            )}
          </ul>
        </div>
      </div>
    </>
  );

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
              Compare named competitors. Dashboard filters (category, source) do not apply here.
            </p>
          )}
        </div>

        {view !== "competitive" && (
          <>
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
        {reasons !== null && view === "dashboard" && (
          <>
            {onAskQuestion && <QuestionsView onAsk={onAskQuestion} />}

            {visibleCorpus && (
              <section className="wi-scrape-panel" aria-label="Scraped unique posts and reviews">
                <div className="wi-scrape-family wi-scrape-family--scraped">
                  <div className="wi-scrape-hero-block">
                    <p className="wi-scrape-kicker">Scraped</p>
                    <p className="wi-scrape-hero">{visibleCorpus.scrapedDocuments.toLocaleString()}</p>
                    <p className="wi-scrape-hero-unit">unique posts &amp; reviews</p>
                    <p className="wi-scrape-hero-note">{visibleCorpus.scrapedMix} One post = one here.</p>
                  </div>
                  <ul className="wi-scrape-sources">
                    {visibleCorpus.scrapedRows.map((row) => {
                      const share = visibleCorpus.scrapedDocuments
                        ? Math.round((row.documents / visibleCorpus.scrapedDocuments) * 100)
                        : 0;
                      const color = SOURCE_COLORS[row.source] ?? "#94a3b8";
                      return (
                        <li
                          key={row.source}
                          className="wi-scrape-source"
                          style={{
                            ["--source-dot" as string]: color,
                            ["--source-fill" as string]: color,
                          }}
                        >
                          <div className="wi-scrape-source-top">
                            <span>{row.label}</span>
                            <strong>
                              {row.documents.toLocaleString()}
                              <em>{share}%</em>
                            </strong>
                          </div>
                          <div className="wi-scrape-source-track" aria-hidden="true">
                            <div
                              className={`wi-scrape-source-fill${row.documents > 0 ? " wi-scrape-source-fill--on" : ""}`}
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

            {voicePreview.length > 0 && (
              <section className="wi-dash-card wi-voice-panel" aria-label="Example shopper comments">
                <h2>Shopper comments</h2>
                <p className="wi-kpi-sub" style={{ marginTop: "-0.55rem", marginBottom: "0.85rem" }}>
                  One real line per reason, from YouTube, Play Store, and reviews.
                </p>
                <ul className="wi-voice-feed">
                  {voicePreview.map((group) => {
                    const line = group.lines[0];
                    if (!line) return null;
                    const tone = VOICE_TONES[group.reason_category] ?? VOICE_TONE_FALLBACK;
                    return (
                      <li
                        key={group.reason_category}
                        style={{
                          ["--voice-bg" as string]: tone.bg,
                          ["--voice-ink" as string]: tone.ink,
                          ["--voice-chip" as string]: tone.chip,
                        }}
                      >
                        <div className="wi-voice-meta">
                          <span className="wi-voice-reason">{formatReason(group.reason_category)}</span>
                          <span className="wi-voice-src">{sourceTag(line.source)}</span>
                        </div>
                        <p className="wi-voice-text">“{line.text}”</p>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            <section className="wi-dash-card">
              <h2>Opportunity Matrix</h2>
              <p className="wi-kpi-sub" style={{ marginTop: "-0.55rem", marginBottom: "0.9rem" }}>
                Ranked by classified evidence — {evidenceTotal.toLocaleString()} excerpts at ≥
                {Math.round(confidenceMin * 100)}% confidence. Long posts can count more than once,
                so this is not the scrape strip total. Share is of the rows shown.
              </p>
              <div className="wi-opp-wrap">
                <div className="wi-opp-table" role="table">
                  <div className="wi-opp-row wi-opp-row--head" role="row">
                    <span role="columnheader">Confidence (0–10)</span>
                    <span role="columnheader">Excerpts</span>
                    <span role="columnheader">Opportunity area</span>
                    <span role="columnheader">Share</span>
                  </div>
                  {reasonBars.map((item, index) => (
                    <div
                      key={item.reason_category}
                      className="wi-opp-row"
                      role="row"
                      style={{ ["--opp-rail" as string]: OPP_RAIL_COLORS[index % OPP_RAIL_COLORS.length] }}
                    >
                      <span role="cell">
                        {item.confidence == null ? "—" : (item.confidence * 10).toFixed(1)}
                      </span>
                      <span role="cell">{item.evidence_volume.toLocaleString()}</span>
                      <span role="cell" className="wi-opp-area">
                        {item.label}
                      </span>
                      <span role="cell">{item.pct}%</span>
                    </div>
                  ))}
                </div>
                {reasonBars.length === 0 && (
                  <p className="wi-reason-empty">
                    Nothing in the current filters is at ≥{Math.round(confidenceMin * 100)}%
                    confidence. Lower the slider or clear a source — most scores sit at 45–63%.
                  </p>
                )}
              </div>
            </section>

            <section className="wi-dash-card wi-pm-calibrate" aria-label="PM calibration">
              <div className="wi-pm-calibrate-head">
                <h2>PM calibration</h2>
                <span>{pmNoteCount}</span>
              </div>
              {pmCalibrationBody}
            </section>
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
