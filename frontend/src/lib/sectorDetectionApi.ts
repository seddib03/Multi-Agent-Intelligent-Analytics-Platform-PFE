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
  const res = await fetch(url("/detect-sector"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_query: userQuery }),
  });

  if (!res.ok) {
    let message = "Erreur lors de la détection du secteur";
    try {
      const data = (await res.json()) as { detail?: string };
      if (data?.detail) message = data.detail;
    } catch {
      // Keep fallback message if response is not JSON.
    }
    throw new Error(message);
  }

  return res.json() as Promise<DetectSectorResponse>;
}
