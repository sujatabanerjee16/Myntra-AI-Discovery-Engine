export interface DashboardFilters {
  run_version: string | null;
  segments: string[];
  categories: string[];
  occasions: string[];
  price_bands: string[];
  reason_categories: string[];
}

export interface ReasonRankItem {
  reason_category: string;
  evidence_volume: number;
  confidence: number | null;
  sources: string[];
  active_shortlist_count: number;
  passive_bookmark_count: number;
}

export interface ReasonRankResponse {
  run_version: string | null;
  reasons: ReasonRankItem[];
  scope_note?: string | null;
}

export interface ComparisonItem {
  dimension: string;
  reason_category: string;
  evidence_volume: number;
  confidence: number | null;
  active_shortlist_count: number;
  passive_bookmark_count: number;
}

export interface ComparisonResponse {
  run_version: string | null;
  group_by: string;
  items: ComparisonItem[];
  respondent_counts?: Record<string, number>;
  age_origin_counts?: Record<string, { survey: number; play_store: number; other_scrape: number }>;
}

export interface SurveyHabitAnswer {
  label: string;
  count: number;
}

export interface SurveyHabitWorkbook {
  file: string;
  n: number;
  question: string | null;
  answers: SurveyHabitAnswer[];
}

export interface SurveyHabitsResponse {
  respondents: number;
  self_reported: boolean;
  checkout_rate_available: boolean;
  workbooks: SurveyHabitWorkbook[];
}

export interface CorpusSourceCount {
  source: string;
  documents: number;
  chunks: number;
}

export interface CorpusWorkbookCount {
  workbook: string;
  respondents: number;
}

export interface CorpusScrapeStats {
  documents: number;
  chunks: number;
  by_source: CorpusSourceCount[];
  survey_documents?: number;
  scraped_documents?: number;
  survey_respondents?: number;
  survey_open_text?: number;
  survey_interviews?: number;
  survey_by_workbook?: CorpusWorkbookCount[];
}

export interface HeatmapCell {
  row: string;
  column: string;
  value: number;
  confidence: number | null;
}

export interface HeatmapResponse {
  run_version: string | null;
  row_key: string;
  column_key: string;
  rows: string[];
  columns: string[];
  cells: HeatmapCell[];
}

export interface IntentBreakdownResponse {
  run_version: string | null;
  total_active: number;
  total_passive: number;
  by_reason: ReasonRankItem[];
}

export interface JourneyTrendItem {
  journey_stage: string;
  evidence_volume: number;
  confidence: number | null;
}

export interface ThemeClusterItem {
  cluster_key: string;
  label: string;
  reason_category: string | null;
  evidence_volume: number;
  confidence: number | null;
  sources: string[];
}

export interface TrendsResponse {
  run_version: string | null;
  journey_stages: JourneyTrendItem[];
  emerging_themes: ThemeClusterItem[];
}

export interface EvidenceExcerpt {
  chunk_id: string;
  text: string;
  source: string;
  source_ref: string | null;
  segment: string | null;
  category: string | null;
  confidence: number | null;
  quality_score: number | null;
}

export interface EvidenceSummaryResponse {
  run_version: string | null;
  reason_category: string;
  evidence_volume: number;
  confidence: number | null;
  sources: string[];
  excerpts: EvidenceExcerpt[];
}

export interface Citation {
  chunk_id: string;
  source: string;
  excerpt: string;
  score: number;
}

export interface AssistantAskResponse {
  trace_id: string | null;
  question: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  limitations: string;
  insufficient_evidence: boolean;
  retrieved_chunk_count: number;
  reason_categories: string[];
}

export interface FilterState {
  segment: string;
  category: string;
  occasion: string;
  price_band: string;
  reason_category: string;
}

export const EMPTY_FILTERS: FilterState = {
  segment: "",
  category: "",
  occasion: "",
  price_band: "",
  reason_category: "",
};

export type IntentType = "high" | "medium" | "low";
export type SourceId =
  | "play_store"
  | "youtube"
  | "reddit"
  | "product_review"
  | "social"
  | "research";
export type PlatformId = "myntra" | "nykaa" | "ajio" | "other";

/**
 * Shared sidebar filter state, lifted to <App /> so a single filter rail
 * drives both the dashboard charts and the Ask AI assistant.
 */
export interface SidebarFilters {
  priceMin: number;
  priceMax: number;
  intentType: IntentType;
  sources: SourceId[];
  confidenceMin: number;
  platforms: PlatformId[];
}

export const DEFAULT_SIDEBAR: SidebarFilters = {
  priceMin: 500,
  priceMax: 5000,
  intentType: "medium",
  sources: ["play_store", "youtube", "reddit", "product_review", "social"],
  confidenceMin: 0.5,
  platforms: ["myntra", "nykaa", "ajio"],
};

export const PLATFORM_META: { id: PlatformId; label: string; color: string }[] = [
  { id: "myntra", label: "Myntra", color: "#ff3e6c" },
  { id: "nykaa", label: "Nykaa", color: "#fc2779" },
  { id: "ajio", label: "Ajio", color: "#3b82f6" },
];

/** Platforms shown on the main dashboard filter rail (hidden; kept for types). */
export const DASHBOARD_PLATFORMS: PlatformId[] = ["myntra", "nykaa"];

/** Named competitors on the competitive view. */
export const COMPETITIVE_PLATFORMS: PlatformId[] = ["myntra", "nykaa", "ajio"];

export function formatLabel(value: string): string {
  const normalized = value.replace(/[_-]+/g, " ").trim().toLowerCase();
  const aliases: Record<string, string> = {
    "price sensitivity": "Price Sensitivity",
    "price sensitivity waiting": "Price Sensitivity",
    "fit sizing issues": "Fit & Sizing Issues",
    "fit and sizing issues": "Fit & Sizing Issues",
    "fit sizing": "Fit & Sizing Issues",
    "product quality concerns": "Product Quality Concerns",
    "product quality": "Product Quality Concerns",
    "styling aesthetics": "Styling & Aesthetics",
    "styling and aesthetics": "Styling & Aesthetics",
    "availability stock": "Availability & Stock",
    "availability and stock": "Availability & Stock",
    "shipping returns policy": "Shipping & Returns Policy",
    "shipping and returns": "Shipping & Returns Policy",
    "other unspecified": "Other / Unspecified",
    "high spenders": "High Spenders",
    "trend seekers": "Trend Seekers",
    "bargain hunters": "Bargain Hunters",
    "new users": "New Users",
    "womens apparel": "Women's Apparel",
    "mens apparel": "Men's Apparel",
    clothing: "Clothing",
    accessories: "Accessories",
    footwear: "Footwear",
    "assortment discovery": "Assortment & Discovery",
    "price sale waiting": "Price / Sale Waiting",
    "brand exclusive": "Brand / Exclusive",
    "category strength": "Category Strength",
    "trust quality": "Trust & Quality",
    "ux convenience": "UX & Convenience",
    "social inspiration": "Social / Inspiration",
    "fit sizing uncertainty": "Fit & Sizing Uncertainty",
    "quality trust doubt": "Quality & Trust Doubt",
    "styling decision uncertainty": "Styling Decision Uncertainty",
    "review trust": "Proof / Photos",
    "timing occasion": "Timing / Occasion",
    "external comparison": "External Comparison",
    "passive bookmarking": "Passive Bookmarking",
    "logistics friction": "Logistics Friction",
    "competitive platform preference": "Competitive Platform Preference",
    "age 18 24": "Age 18–24",
    "age 25 35": "Age 25–35",
  };
  if (aliases[normalized]) return aliases[normalized];
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
}

export function confidenceColor(confidence: number | null): string {
  if (confidence === null) return "#94a3b8";
  if (confidence >= 0.75) return "#059669";
  if (confidence >= 0.5) return "#d97706";
  return "#dc2626";
}

export interface EvalRunRecord {
  id: string;
  run_version: string;
  retrieval_hit_at_k: number | null;
  retrieval_mrr: number | null;
  faithfulness_score: number | null;
  taxonomy_accuracy: number | null;
  passed: boolean;
  created_at: string;
}

export interface EvalSummaryResponse {
  latest: EvalRunRecord | null;
  targets: {
    retrieval_hit: number;
    faithfulness: number;
    taxonomy_accuracy: number;
  };
  thresholds: {
    rag_min_top_score: number;
    rag_min_avg_score: number;
  };
  cost_controls: Record<string, unknown>;
}

export interface RagTraceSummary {
  id: string;
  question: string;
  confidence: number | null;
  insufficient_evidence: boolean | null;
  duration_ms: number | null;
  created_at: string;
}

export interface PipelineRunRecord {
  id: string;
  run_type: string;
  run_version: string;
  success: boolean;
  duration_ms: number | null;
  stats: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
}

export interface QualityDashboardResponse {
  eval_summary: EvalSummaryResponse;
  recent_traces: RagTraceSummary[];
  recent_pipeline_runs: PipelineRunRecord[];
  corpus_stats: Record<string, unknown>;
}

export interface CostControlsResponse {
  enabled: {
    embedding_cache: boolean;
    retrieval_cache: boolean;
  };
  caches: {
    embedding_cache?: {
      hits: number;
      misses: number;
      hit_rate: number;
      entries: number;
    };
    retrieval_cache?: {
      hits: number;
      misses: number;
      hit_rate: number;
      entries: number;
    };
  };
}

export interface ConversionMetricResponse {
  run_version: string;
  window_days: number;
  wishlist_users: number;
  converted_users: number;
  conversion_rate: number;
  non_conversion_rate: number;
  cohort_start: string | null;
  cohort_end: string | null;
}

export interface ReasonCorroborationItem {
  reason_category: string;
  public_confidence: number | null;
  public_evidence_volume: number;
  internal_non_conversion_share: number | null;
  corroboration_score: number;
  status: string;
  segment_affinity: string[];
}

export interface CorroborationResponse {
  run_version: string;
  conversion_rate: number | null;
  items: ReasonCorroborationItem[];
}

export interface InsightFeedbackRecord {
  id: string;
  insight_id: string | null;
  reason_category: string;
  verdict: string;
  notes: string | null;
  reviewer: string;
  adjusted_confidence: number | null;
  created_at: string;
}

export interface InsightFeedbackListResponse {
  total: number;
  feedback: InsightFeedbackRecord[];
}

export interface CompetitiveMetricItem {
  platform: string;
  metric_type: string;
  label: string;
  count: number;
  share: number | null;
  evidence_volume: number;
  confidence: number | null;
  shared_vs_unique: string | null;
  sources: string[];
}

export interface CompetitiveTopItem {
  label: string;
  count: number;
  share: number | null;
  confidence: number | null;
}

export interface CompetitiveAnalysisResponse {
  run_version: string | null;
  platforms: string[];
  motives: CompetitiveMetricItem[];
  barriers: CompetitiveMetricItem[];
  shared_motives: string[];
  unique_motives_by_platform: Record<string, string[]>;
  top_motive_by_platform: Record<string, CompetitiveTopItem>;
  top_barrier_by_platform: Record<string, CompetitiveTopItem>;
  why_not_purchase: string[];
  limitations: string;
}
