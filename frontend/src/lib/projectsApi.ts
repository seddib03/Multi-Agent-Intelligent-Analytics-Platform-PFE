import { ensureValidSession } from "./mockAuth";
import type { SectorDetectionContext } from "@/types/app";

const API_BASE_URL =
  (import.meta.env.VITE_BACKEND_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8005";

function url(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function authHeaders(): Promise<HeadersInit> {
  const session = await ensureValidSession();
  if (!session) throw new Error("Session expirée. Veuillez vous reconnecter.");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    try {
      const data = await res.json();
      throw new Error(data?.detail || "Erreur serveur");
    } catch {
      throw new Error("Erreur serveur");
    }
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export type ProjectStatus =
  | "CREATED"
  | "DATA_UPLOADED"
  | "METADATA_CONFIGURED"
  | "TRAINING"
  | "READY"
  | "FAILED"
  | "ARCHIVED";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  use_case: string | null;
  detected_sector: string | null;
  visual_preferences: string | null;
  status: ProjectStatus;
  business_rules: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  use_case?: string;
  visual_preferences?: Record<string, unknown>;
  business_rules?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  use_case?: string;
  visual_preferences?: Record<string, unknown>;
  business_rules?: string;
  status?: ProjectStatus;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export async function listProjects(): Promise<Project[]> {
  const headers = await authHeaders();
  const res = await fetch(url("/api/projects"), { headers });
  return handleResponse<Project[]>(res);
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  const headers = await authHeaders();
  const res = await fetch(url("/api/projects"), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  return handleResponse<Project>(res);
}

export async function getProject(projectId: string): Promise<Project> {
  const headers = await authHeaders();
  const res = await fetch(url(`/api/projects/${projectId}`), { headers });
  return handleResponse<Project>(res);
}

export async function updateProject(projectId: string, body: ProjectUpdate): Promise<Project> {
  const headers = await authHeaders();
  const res = await fetch(url(`/api/projects/${projectId}`), {
    method: "PUT",
    headers,
    body: JSON.stringify(body),
  });
  return handleResponse<Project>(res);
}

export async function deleteProject(projectId: string): Promise<void> {
  const headers = await authHeaders();
  const res = await fetch(url(`/api/projects/${projectId}`), {
    method: "DELETE",
    headers,
  });
  return handleResponse<void>(res);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseProjectVisualPreferences(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function getProjectSectorContext(project: Project): SectorDetectionContext | null {
  const visualPreferences = parseProjectVisualPreferences(project.visual_preferences);
  const context = visualPreferences?.sectorContext;
  if (!isRecord(context)) return null;

  if (
    typeof context.sector !== "string" ||
    typeof context.confidence !== "number" ||
    typeof context.dashboard_focus !== "string"
  ) {
    return null;
  }

  return context as unknown as SectorDetectionContext;
}