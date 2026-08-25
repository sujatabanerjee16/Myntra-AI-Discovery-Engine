import type {
  AssistantAskResponse,
  ComparisonResponse,
  CompetitiveAnalysisResponse,
  ConversionMetricResponse,
  CorroborationResponse,
  CostControlsResponse,
  DashboardFilters,
  EvidenceSummaryResponse,
  FilterState,
  HeatmapResponse,
  InsightFeedbackListResponse,
  InsightFeedbackRecord,
  IntentBreakdownResponse,
  QualityDashboardResponse,
  ReasonRankResponse,
  TrendsResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

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

function filterParams(filters: FilterState): Record<string, string | undefined> {
  return {
    segment: filters.segment || undefined,
    category: filters.category || undefined,
    occasion: filters.occasion || undefined,
    price_band: filters.price_band || undefined,
    reason_category: filters.reason_category || undefined,
  };
}

async function fetchJson<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export async function getFilters(): Promise<DashboardFilters> {
  return fetchJson(apiUrl("/insights/filters"));
}

export async function getRankedReasons(filters: FilterState): Promise<ReasonRankResponse> {
  return fetchJson(apiUrl(`/insights/reasons${buildQuery(filterParams(filters))}`));
}

export async function getComparisons(filters: FilterState): Promise<ComparisonResponse> {
  return fetchJson(apiUrl(`/insights/comparisons${buildQuery({ group_by: "segment", ...filterParams(filters) })}`));
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
  
  const resp = await fetch(apiUrl("/assistant/ask"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`);
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
