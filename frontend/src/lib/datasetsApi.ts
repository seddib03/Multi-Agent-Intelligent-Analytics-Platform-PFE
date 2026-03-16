import { ensureValidSession } from "./mockAuth";

const API_BASE_URL =
  (import.meta.env.VITE_BACKEND_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8005";

function url(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function getToken(): Promise<string> {
  const session = await ensureValidSession();
  if (!session) throw new Error("Session expirée. Veuillez vous reconnecter.");
  return session.access_token;
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
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ColumnProfile {
  original_name: string;
  detected_type: string;
  null_percent:  number;
  unique_count:  number;
  sample_values: unknown[];
  stats?:        Record<string, unknown>;
}

export interface UploadResponse {
  file_id:           string;
  original_filename: string;
  row_count:         number;
  column_count:      number;
  file_size_bytes:   number;
  detected_sector:   string | null;
  quality_score:     number;
  preview:           Record<string, unknown>[];
  columns:           ColumnProfile[];
}

export interface DictionaryUploadResponse {
  original_filename: string;
  stored_path:       string;
  file_size_bytes:   number;
}

export interface QualityIssue {
  type:     string;
  severity: string;
  message:  string;
  fix:      string;
}

export interface ColumnQuality {
  column:  string;
  issues:  QualityIssue[];
  score:   number;
}

export interface QualityReport {
  dataset_id:            string;
  global_score:          number;
  total_columns:         number;
  columns_ok:            number;
  columns_issues:        number;
  critical_count:        number;
  warning_count:         number;
  issues:                ColumnQuality[];
  corrections_available: string[];
}

export interface DatasetMetadataColumnUpdate {
  original_name: string;
  business_name?: string;
  semantic_type?: string;
  description?: string;
  [key: string]: unknown;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export async function uploadDataset(
  projectId: string,
  file: File,
): Promise<UploadResponse> {
  const token = await getToken();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(url(`/api/projects/${projectId}/datasets/upload`), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return handleResponse<UploadResponse>(res);
}

export async function analyzeQuality(
  projectId: string,
  datasetId: string,
): Promise<QualityReport> {
  const token = await getToken();
  const res = await fetch(
    url(`/api/projects/${projectId}/datasets/${datasetId}/analyze-quality`),
    { method: "POST", headers: { Authorization: `Bearer ${token}` } },
  );
  return handleResponse<QualityReport>(res);
}

export async function getQualityReport(
  projectId: string,
  datasetId: string,
): Promise<QualityReport> {
  const token = await getToken();
  const res = await fetch(
    url(`/api/projects/${projectId}/datasets/${datasetId}/quality-report`),
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return handleResponse<QualityReport>(res);
}

export async function applyCorrections(
  projectId: string,
  datasetId: string,
  corrections: string[],
): Promise<{ applied: string[]; skipped: string[]; message: string }> {
  const token = await getToken();
  const res = await fetch(
    url(`/api/projects/${projectId}/datasets/${datasetId}/apply-corrections`),
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ corrections }),
    },
  );
  return handleResponse(res);
}

export async function uploadDatasetDictionary(
  projectId: string,
  file: File,
  datasetName: string,
): Promise<DictionaryUploadResponse> {
  const token = await getToken();
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams({ dataset_name: datasetName });
  const res = await fetch(url(`/api/projects/${projectId}/datasets/dictionary/upload?${params}`), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  return handleResponse<DictionaryUploadResponse>(res);
}

export async function updateDatasetMetadata(
  projectId: string,
  datasetId: string,
  columns: DatasetMetadataColumnUpdate[],
): Promise<void> {
  const token = await getToken();
  const res = await fetch(url(`/api/projects/${projectId}/datasets/${datasetId}/metadata`), {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ columns }),
  });

  await handleResponse(res);
}