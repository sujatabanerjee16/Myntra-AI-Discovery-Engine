import type {
  AssistantAskResponse,
  CompetitiveAnalysisResponse,
  ConversionMetricResponse,
  CorpusScrapeStats,
  CorroborationResponse,
  CostControlsResponse,
  DashboardFilters,
  EvidenceSummaryResponse,
  FilterState,
  HeatmapResponse,
  IntentType,
  PlatformId,
  SourceId,
  InsightFeedbackListResponse,
  InsightFeedbackRecord,
  IntentBreakdownResponse,
  QualityDashboardResponse,
  ReasonRankResponse,
  TrendsResponse,
  DashboardBootstrap,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

const FETCH_TIMEOUT_MS = 20_000;
const HEALTH_TIMEOUT_MS = 45_000;
const ASSISTANT_TIMEOUT_MS = 120_000;

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

function slugFilter(value: string | undefined): string | undefined {
  if (!value) return undefined;
  return value.trim().toLowerCase().replace(/[–—\s-]+/g, "_") || undefined;
}

function filterParams(filters: FilterState): Record<string, string | undefined> {
  return {
    segment: slugFilter(filters.segment),
    category: slugFilter(filters.category),
    occasion: slugFilter(filters.occasion),
    price_band: slugFilter(filters.price_band),
    reason_category: slugFilter(filters.reason_category),
  };
}

async function fetchJson<T>(path: string, timeoutMs: number = FETCH_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(path, { signal: controller.signal });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const body = (await resp.json()) as { detail?: unknown };
        if (body.detail) {
          detail = `${detail}: ${typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)}`;
        }
      } catch {
        /* keep status text */
      }
      throw new Error(detail);
    }
    return resp.json() as Promise<T>;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function wakeApi(): Promise<boolean> {
  try {
    await fetchJson<{ status?: string }>(apiUrl("/health"), HEALTH_TIMEOUT_MS);
    return true;
  } catch {
    return false;
  }
}

export async function getStaticDashboardBootstrap(): Promise<DashboardBootstrap | null> {
  try {
    const payload = await fetchJson<DashboardBootstrap>("/dashboard-bootstrap.json", 8_000);
    if (!payload?.reasons || !payload?.filters) return null;
    return payload;
  } catch {
    return null;
  }
}

export async function getDashboardBootstrap(): Promise<DashboardBootstrap> {
  return fetchJson(apiUrl("/insights/bootstrap"));
}

export async function getFilters(): Promise<DashboardFilters> {
  return fetchJson(apiUrl("/insights/filters"));
}

export interface ReasonQuery {
  minConfidence?: number;
  sources?: SourceId[];
  platforms?: PlatformId[];
  intentType?: IntentType;
}

export async function getRankedReasons(
  filters: FilterState,
  query: number | ReasonQuery = {},
): Promise<ReasonRankResponse> {
  const options: ReasonQuery = typeof query === "number" ? { minConfidence: query } : query;
  const intent =
    options.intentType === "high"
      ? "active_shortlist"
      : options.intentType === "low"
        ? "passive_bookmark"
        : undefined;
  const sourceList = options.sources ?? [];
  const platformList = options.platforms ?? [];
  return fetchJson(
    apiUrl(
      `/insights/reasons${buildQuery({
        ...filterParams(filters),
        min_confidence: options.minConfidence != null ? String(options.minConfidence) : undefined,
        sources: sourceList.length > 0 ? sourceList.join(",") : undefined,
        platforms: platformList.length > 0 ? platformList.join(",") : undefined,
        intent,
      })}`,
    ),
  );
}

export async function getCorpusStats(): Promise<CorpusScrapeStats> {
  return fetchJson(apiUrl("/insights/corpus-stats"));
}

export async function getHeatmap(filters: FilterState): Promise<HeatmapResponse> {
  return fetchJson(apiUrl(`/insights/heatmap${buildQuery(filterParams(filters))}`));
}

export async function getIntentBreakdown(filters: FilterState): Promise<IntentBreakdownResponse> {
  return fetchJson(apiUrl(`/insights/intent${buildQuery(filterParams(filters))}`));
}

export async function getTrends(): Promise<TrendsResponse> {
  return fetchJson(apiUrl("/insights/trends"));
}

export async function getCompetitiveAnalysis(): Promise<CompetitiveAnalysisResponse> {
  return fetchJson(apiUrl("/insights/competitive"));
}

export async function getEvidence(reasonCategory: string, filters: FilterState): Promise<EvidenceSummaryResponse> {
  return fetchJson(
    apiUrl(`/insights/evidence${buildQuery({ reason_category: reasonCategory, ...filterParams(filters) })}`),
  );
}

export async function askAssistant(question: string, platforms?: string[]): Promise<AssistantAskResponse> {
  // Always include the filters if we have platforms
  const payload: any = { question, persist_trace: true };
  if (platforms && platforms.length > 0) {
    payload.platforms = platforms;
  }
  
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), ASSISTANT_TIMEOUT_MS);
  const resp = await fetch(apiUrl("/assistant/ask"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: controller.signal,
  }).finally(() => window.clearTimeout(timer));
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = (await resp.json()) as { detail?: unknown };
      if (Array.isArray(body.detail) && body.detail.length > 0) {
        const first = body.detail[0] as { msg?: string };
        if (first?.msg) detail = first.msg;
      } else if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<AssistantAskResponse>;
}

export async function getKeyQuestions(): Promise<string[]> {
  const body = await fetchJson<{ questions: string[] }>(apiUrl("/assistant/questions"));
  return body.questions;
}

export async function getQualityDashboard(): Promise<QualityDashboardResponse> {
  return fetchJson(apiUrl("/observability/quality"));
}

export async function getCostControls(): Promise<CostControlsResponse> {
  return fetchJson(apiUrl("/observability/cost-controls"));
}

export async function runEvaluation(): Promise<{ passed: boolean; run_version: string }> {
  const resp = await fetch(apiUrl("/observability/eval/run"), { method: "POST" });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
  }
  return resp.json() as Promise<{ passed: boolean; run_version: string }>;
}

export async function getConversionMetric(): Promise<ConversionMetricResponse> {
  return fetchJson(apiUrl("/internal/conversion"));
}

export async function getCorroboration(): Promise<CorroborationResponse> {
  return fetchJson(apiUrl("/internal/corroboration"));
}

export async function runInternalCompute(): Promise<Record<string, unknown>> {
  const resp = await fetch(apiUrl("/internal/compute"), { method: "POST" });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<Record<string, unknown>>;
}

export async function submitInsightFeedback(body: {
  reason_category: string;
  verdict: string;
  notes?: string;
  insight_id?: string;
}): Promise<InsightFeedbackRecord> {
  const resp = await fetch(apiUrl("/internal/feedback"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const payload = (await resp.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<InsightFeedbackRecord>;
}

export async function listInsightFeedback(): Promise<InsightFeedbackListResponse> {
  return fetchJson(apiUrl("/internal/feedback"));
}
