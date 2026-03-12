const ORCHESTRATOR_API_BASE_URL =
  (import.meta.env.VITE_ORCHESTRATOR_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8003";

function url(path: string) {
  return `${ORCHESTRATOR_API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export interface InsightKpi {
  name: string;
  value?: number | string | null;
}

export interface InsightChart {
  type?: string;
  title?: string;
  x?: string;
  y?: string;
  data?: Record<string, unknown>[];
}

export interface AnalyzeResponse {
  response_format?: "text" | "kpi" | "chart" | "table" | string;
  final_response?: string;
  needs_clarification?: boolean;
  clarification_question?: string;
  agent_response?: {
    kpis?: InsightKpi[];
    charts?: InsightChart[];
    insights?: string[];
  };
}

export async function analyzeOrchestrator(params: {
  queryRaw: string;
  datasetFile?: File | null;
  metadata?: Record<string, unknown>;
}): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("query_raw", params.queryRaw);

  if (params.datasetFile) {
    formData.append("dataset", params.datasetFile);
  }

  formData.append("metadata", JSON.stringify(params.metadata ?? {}));

  const res = await fetch(url("/analyze"), {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let message = "Erreur serveur sur /analyze";
    try {
      const data = (await res.json()) as { detail?: string };
      if (data?.detail) message = data.detail;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }

  return (await res.json()) as AnalyzeResponse;
}