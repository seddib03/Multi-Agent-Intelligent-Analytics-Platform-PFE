import { ensureValidSession } from "@/lib/mockAuth";
import type { ChartData, Entity } from "@/types/app";

const ORCHESTRATOR_URL =
  (import.meta.env.VITE_ORCHESTRATOR_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8003";

export interface OrchestratorResponse {
  user_id:                string;
  session_id:             string;
  query_raw:              string;
  response?:              string;
  final_response?:        string;
  response_format:        "text" | "kpi" | "chart" | "table";
  route_taken?:           string;
  route_reason:           string;
  sector_detected?:       string;
  sector?:                string;
  intent_detected?:       string;
  intent?:                string;
  needs_clarification:    boolean;
  clarification_question: string;
  data_payload?:          Record<string, unknown>;
  agent_response?:        Record<string, unknown>;
}

export interface ParsedOrchestratorResult {
  text:                  string;
  charts?:               ChartData[];
  predictions?:          Entity[];
  needsClarification:    boolean;
  clarificationQuestion: string;
  kpis?:                 { name: string; value: number; unit: string }[];
}

export interface OrchestratorMeta {
  sector:       string;
  use_case:     string;
  dataset_name: string;
  row_count:    number;
  column_count: number;
  columns:      { name: string; type: string; original: string }[];
}

export async function callOrchestrator(
  queryRaw: string,
  metadata: OrchestratorMeta,
  csvPath?: string | null,
  csvFile?: File | null,
): Promise<OrchestratorResponse> {
  try { await ensureValidSession(); } catch { /* orchestrator may not require auth */ }

  const form = new FormData();
  form.append("query_raw", queryRaw);
  form.append("metadata", JSON.stringify(metadata));

  if (csvPath) {
    form.append("csv_path", csvPath);
  } else if (csvFile) {
    form.append("dataset", csvFile, csvFile.name);
  }

  const res = await fetch(`${ORCHESTRATOR_URL}/analyze`, {
    method: "POST",
    body:   form,
  });

  if (!res.ok) {
    let detail = `Orchestrateur — erreur ${res.status}`;
    try {
      const data = await res.json() as { detail?: string };
      if (data?.detail) detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }

  return res.json() as Promise<OrchestratorResponse>;
}

export function parseOrchestratorResponse(
  raw: OrchestratorResponse,
): ParsedOrchestratorResult {
  const text =
    raw.response ||
    raw.final_response ||
    raw.clarification_question ||
    "Aucune réponse reçue.";

  const result: ParsedOrchestratorResult = {
    text,
    needsClarification:    raw.needs_clarification,
    clarificationQuestion: raw.clarification_question,
  };

  // Chercher les données dans data_payload ou agent_response
  const payload    = raw.data_payload    ?? {};
  const agentResp  = raw.agent_response  ?? {};

  // ── KPIs ────────────────────────────────────────────────────────────────
  const kpisSource = Array.isArray(payload.kpis) ? payload.kpis
                   : Array.isArray(agentResp.kpis) ? agentResp.kpis
                   : null;

  if (kpisSource) {
    const kpis = (kpisSource as { name: string; value: number; unit?: string }[])
      .filter((k) => k.value != null);
    if (kpis.length > 0) {
      result.kpis = kpis.map((k) => ({ name: k.name, value: k.value, unit: k.unit ?? "" }));
      const kpiLines = kpis.map((k) => `**${k.name}** : ${k.value} ${k.unit ?? ""}`).join("\n");
      result.text = `${text}\n\n${kpiLines}`;
    }
  }

  // ── Charts ───────────────────────────────────────────────────────────────
  const chartsSource = Array.isArray(payload.charts) ? payload.charts
                     : Array.isArray(agentResp.charts) ? agentResp.charts
                     : null;

  if (chartsSource) {
    result.charts = (chartsSource as Record<string, unknown>[]).map((c) => ({
      type:     (["bar","line","pie","area"].includes(c.type as string) ? c.type : "bar") as "bar" | "line" | "pie" | "area",
      title:    (c.title as string) ?? "",
      data:     Array.isArray(c.data) ? c.data as Record<string, unknown>[] : [],
      dataKeys: Array.isArray(c.dataKeys) ? c.dataKeys as string[] : ["value"],
    }));
  }

  // ── Table / predictions ──────────────────────────────────────────────────
  if (raw.response_format === "table" && Array.isArray(payload.rows)) {
    result.predictions = payload.rows as Entity[];
  }

  return result;
}