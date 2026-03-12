export interface SectorKpi {
  name: string;
  description: string;
  unit: string;
  priority: string;
}

export interface DetectSectorResponse {
  sector: string;
  confidence: number;
  use_case: string;
  metadata_used: boolean;
  kpis: SectorKpi[];
  dashboard_focus: string;
  recommended_charts: string[];
  routing_target: string;
  explanation: string;
}

const SECTOR_API_BASE_URL =
  (import.meta.env.VITE_SECTOR_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8002";

function url(path: string): string {
  return `${SECTOR_API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function detectSector(userQuery: string): Promise<DetectSectorResponse> {
  // the frontend may call a dedicated sector microservice (port 8002 by default)
  // but in development we often only have the main backend running on 8000.
  // try the primary URL first, and fall back to the backend endpoint if it fails.
  // by default the frontend talks to the backend directly; override with VITE_SECTOR_API_URL if you
  // really have a separate service running on 8002 or elsewhere.  if the env variable is not set or
  // points to a non‑existent host the fetch will simply be retried once against the backend
  // without spamming the console.
  const primary = url("/detect-sector");
  const fallback = "http://localhost:8000/api/sector/detect-sector";

  async function post(urlToCall: string) {
    const response = await fetch(urlToCall, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_query: userQuery }),
    });
    if (!response.ok) {
      const data = await response.text();
      let message = `Erreur ${response.status} lors de la détection du secteur`;
      try {
        const json = JSON.parse(data);
        if (json?.detail) message = json.detail;
      } catch {
        // ignore
      }
      throw new Error(message);
    }
    return response.json() as Promise<DetectSectorResponse>;
  }

  try {
    return await post(primary);
  } catch (e) {
    // don't log 404/connection errors when primary API is missing; just use backend silently
    return await post(fallback);
  }
}
