import { ensureValidSession } from "@/lib/mockAuth";
import type { ChartData, Entity } from "@/types/app";

const ORCHESTRATOR_URL =
  (import.meta.env.VITE_ORCHESTRATOR_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8003";

export interface OrchestratorResponse {
  user_id:               string;
  session_id:            string;
  query_raw:             string;
  response:              string;
  response_format:       "text" | "kpi" | "chart" | "table";
  route_taken?:          string;
  route_reason:          string;
  sector_detected:       string;
  intent_detected:       string;
  needs_clarification:   boolean;
  clarification_question: string;
  data_payload:          Record<string, unknown>;
}

export interface ParsedOrchestratorResult {
  text:        string;
  charts?:     ChartData[];
  predictions?: Entity[];
  needsClarification: boolean;
  clarificationQuestion: string;
}

/**
 * Sends a user query to the orchestrator.
 * @param queryRaw     The user's natural language question
 * @param csvPath      Optional — path already stored on server (not re-uploaded)
 * @param metadata     Optional metadata dict
 */
export async function callOrchestrator(
  queryRaw:  string,
  metadata:  Record<string, unknown> = {},
): Promise<OrchestratorResponse> {
  // Token not strictly required by orchestrator but included for consistency
  try { await ensureValidSession(); } catch { /* orchestrator may not require auth */ }

  const form = new FormData();
  form.append("query_raw", queryRaw);
  form.append("metadata", JSON.stringify(metadata));

  const res = await fetch(`${ORCHESTRATOR_URL}/analyze`, {
    method: "POST",
    body: form,
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

/**
 * Maps the raw OrchestratorResponse to the Message-compatible format.
 */
export function parseOrchestratorResponse(
  raw: OrchestratorResponse,
): ParsedOrchestratorResult {
  const result: ParsedOrchestratorResult = {
    text:                  raw.response || "Aucune réponse reçue.",
    needsClarification:    raw.needs_clarification,
    clarificationQuestion: raw.clarification_question,
  };

  const payload = raw.data_payload ?? {};

  // ── KPIs → texte enrichi si format kpi ─────────────────────────────────
  if (raw.response_format === "kpi" && Array.isArray(payload.kpis)) {
    const kpiLines = (payload.kpis as { name: string; value: number; unit: string }[])
      .map((k) => `**${k.name}** : ${k.value} ${k.unit}`)
      .join("\n");
    result.text = `${raw.response}\n\n${kpiLines}`;
  }

  // ── Charts ──────────────────────────────────────────────────────────────
  if (Array.isArray(payload.charts)) {
    result.charts = (payload.charts as ChartData[]);
  }

  // ── Predictions / table ─────────────────────────────────────────────────
  if (raw.response_format === "table" && Array.isArray(payload.rows)) {
    result.predictions = (payload.rows as Entity[]);
  }

  return result;
}