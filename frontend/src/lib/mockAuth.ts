export interface MockUser {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  user_metadata?: {
    full_name?: string;
  };
}

export interface MockSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: number;
  user: MockUser;
}

interface AuthResponse {
  data: {
    user: MockUser | null;
    session: MockSession | null;
  };
  error: { message: string } | null;
}

interface BackendUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
  created_at: string;
}

export interface BackendPreferences {
  dark_mode?: boolean;
  chart_style?: string;
  density?: string;
  accent_theme?: string;
  primary_color?: string;
  secondary_color?: string;
  dashboard_layout?: string;
  visible_kpis?: string[];
}

export interface BackendUserProfile extends BackendUser {
  preferences?: BackendPreferences;
}

interface BackendAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: BackendUser;
}

const SESSION_STORAGE_KEY = "app-auth-session";
export const AUTH_STATE_EVENT = "app-auth-state-changed";

const API_BASE_URL = (import.meta.env.VITE_BACKEND_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

function getAuthUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d?.msg).filter(Boolean).join("; ") || "Requete invalide";
    return data?.message || "Erreur serveur";
  } catch {
    return "Erreur serveur";
  }
}

async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const response = await fetch(getAuthUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }

  return (await response.json()) as T;
}

async function putJson<T>(path: string, body: unknown, token: string): Promise<T> {
  const response = await fetch(getAuthUrl(path), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }

  return (await response.json()) as T;
}

async function deleteRequest(path: string, token: string): Promise<void> {
  const response = await fetch(getAuthUrl(path), {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }
}

async function getJson<T>(path: string, token: string): Promise<T> {
  const response = await fetch(getAuthUrl(path), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }

  return (await response.json()) as T;
}

function decodeJwtExpiry(token: string): number {
  try {
    const payload = token.split(".")[1];
    if (!payload) return Date.now() + 60 * 60 * 1000;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(atob(normalized)) as { exp?: number };
    return decoded.exp ? decoded.exp * 1000 : Date.now() + 60 * 60 * 1000;
  } catch {
    return Date.now() + 60 * 60 * 1000;
  }
}

function toFrontendUser(user: BackendUser): MockUser {
  const full_name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
  return {
    id: user.id,
    email: user.email,
    first_name: user.first_name,
    last_name: user.last_name,
    company_name: user.company_name,
    user_metadata: { full_name },
  };
}

function buildSessionFromBackend(data: BackendAuthResponse): MockSession {
  return {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    token_type: data.token_type || "bearer",
    expires_at: decodeJwtExpiry(data.access_token),
    user: toFrontendUser(data.user),
  };
}

function mergeUserIntoSession(user: BackendUserProfile, current: MockSession): MockSession {
  return {
    ...current,
    user: toFrontendUser(user),
  };
}

function writeSession(session: MockSession | null) {
  if (session) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(AUTH_STATE_EVENT));
}

function readSession(): MockSession | null {
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MockSession;
  } catch {
    return null;
  }
}

function splitFullName(fullName?: string): { first_name: string; last_name: string } {
  const name = (fullName || "").trim();
  if (!name) return { first_name: "User", last_name: "" };
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return { first_name: parts[0], last_name: "" };
  return {
    first_name: parts[0],
    last_name: parts.slice(1).join(" "),
  };
}

export function getCurrentSession(): MockSession | null {
  return readSession();
}

export async function ensureValidSession(): Promise<MockSession | null> {
  const current = readSession();
  if (!current) return null;

  if (current.expires_at > Date.now() + 5000) {
    return current;
  }

  if (!current.refresh_token) {
    writeSession(null);
    return null;
  }

  try {
    const refreshed = await postJson<{ access_token: string; refresh_token: string; token_type?: string }>(
      "/api/auth/refresh",
      { refresh_token: current.refresh_token }
    );

    const me = await getJson<BackendUser>("/api/auth/users/me", refreshed.access_token);
    const next: MockSession = {
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token,
      token_type: refreshed.token_type || current.token_type || "bearer",
      expires_at: decodeJwtExpiry(refreshed.access_token),
      user: toFrontendUser(me),
    };
    writeSession(next);
    return next;
  } catch {
    writeSession(null);
    return null;
  }
}

export async function authGetMe(): Promise<{ data: BackendUserProfile | null; error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { data: null, error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    const data = await getJson<BackendUserProfile>("/api/auth/users/me", current.access_token);
    writeSession(mergeUserIntoSession(data, current));
    return { data, error: null };
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : "Echec get me auth" } };
  }
}

export async function authUpdateMe(payload: { first_name?: string; last_name?: string; email?: string }): Promise<{ data: BackendUserProfile | null; error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { data: null, error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await putJson<unknown>("/api/auth/users/me", payload, current.access_token);
    const me = await getJson<BackendUserProfile>("/api/auth/users/me", current.access_token);
    writeSession(mergeUserIntoSession(me, current));
    return { data: me, error: null };
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : "Echec update me auth" } };
  }
}

export async function authDeleteMe(): Promise<{ error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await deleteRequest("/api/auth/users/me", current.access_token);
    writeSession(null);
    return { error: null };
  } catch (error) {
    return { error: { message: error instanceof Error ? error.message : "Echec suppression compte auth" } };
  }
}

export async function authUpdatePreferences(payload: BackendPreferences): Promise<{ error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await putJson<unknown>("/api/auth/users/me/preferences", payload, current.access_token);
    return { error: null };
  } catch (error) {
    return { error: { message: error instanceof Error ? error.message : "Echec update preferences auth" } };
  }
}

export async function usersGetMe(): Promise<{ data: BackendUserProfile | null; error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { data: null, error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    const data = await getJson<BackendUserProfile>("/api/users/me", current.access_token);
    writeSession(mergeUserIntoSession(data, current));
    return { data, error: null };
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : "Echec get me users" } };
  }
}

export async function usersUpdateMe(payload: { first_name?: string; last_name?: string; email?: string }): Promise<{ data: BackendUserProfile | null; error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { data: null, error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await putJson<unknown>("/api/users/me", payload, current.access_token);
    const me = await getJson<BackendUserProfile>("/api/users/me", current.access_token);
    writeSession(mergeUserIntoSession(me, current));
    return { data: me, error: null };
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : "Echec update me users" } };
  }
}

export async function usersDeleteMe(): Promise<{ error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await deleteRequest("/api/users/me", current.access_token);
    writeSession(null);
    return { error: null };
  } catch (error) {
    return { error: { message: error instanceof Error ? error.message : "Echec suppression compte users" } };
  }
}

export async function usersUpdatePreferences(payload: BackendPreferences): Promise<{ error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) return { error: { message: "Session expiree. Veuillez vous reconnecter." } };

  try {
    await putJson<unknown>("/api/users/me/preferences", payload, current.access_token);
    return { error: null };
  } catch (error) {
    return { error: { message: error instanceof Error ? error.message : "Echec update preferences users" } };
  }
}

export async function signInWithPassword({
  email,
  password,
}: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  try {
    const data = await postJson<BackendAuthResponse>("/api/auth/login", {
      email: email.trim().toLowerCase(),
      password,
    });
    const session = buildSessionFromBackend(data);
    writeSession(session);
    return { data: { user: session.user, session }, error: null };
  } catch (error) {
    return {
      data: { user: null, session: null },
      error: { message: error instanceof Error ? error.message : "Echec de connexion" },
    };
  }
}

export async function signUp({
  email,
  password,
  options,
}: {
  email: string;
  password: string;
  options?: { data?: { full_name?: string; company_name?: string } };
}): Promise<AuthResponse> {
  try {
    const { first_name, last_name } = splitFullName(options?.data?.full_name);
    const company_name = (options?.data?.company_name || (import.meta.env.VITE_DEFAULT_COMPANY_NAME as string | undefined) || "Default").trim();

    const data = await postJson<BackendAuthResponse>("/api/auth/register", {
      email: email.trim().toLowerCase(),
      password,
      first_name,
      last_name,
      company_name,
    });
    const session = buildSessionFromBackend(data);
    writeSession(session);
    return { data: { user: session.user, session }, error: null };
  } catch (error) {
    return {
      data: { user: null, session: null },
      error: { message: error instanceof Error ? error.message : "Echec de creation du compte" },
    };
  }
}

export async function signOut(): Promise<void> {
  const current = readSession();
  if (current?.refresh_token) {
    try {
      await postJson<{ message: string }>("/api/auth/logout", { refresh_token: current.refresh_token });
    } catch {
      // Ignore logout API errors and clear local session anyway.
    }
  }
  writeSession(null);
}

export async function updateProfile({
  userId: _userId,
  fullName,
}: {
  userId: string;
  fullName: string;
}): Promise<{ error: { message: string } | null }> {
  const current = await ensureValidSession();
  if (!current) {
    return { error: { message: "Session expiree. Veuillez vous reconnecter." } };
  }

  const { first_name, last_name } = splitFullName(fullName);

  try {
    await usersUpdateMe({ first_name, last_name });

    const updatedUser: MockUser = {
      ...current.user,
      first_name,
      last_name,
      user_metadata: { full_name: `${first_name} ${last_name}`.trim() },
    };
    writeSession({ ...current, user: updatedUser });
    return { error: null };
  } catch (error) {
    return {
      error: { message: error instanceof Error ? error.message : "Echec de mise a jour du profil" },
    };
  }
}
