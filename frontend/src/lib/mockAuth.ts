export interface MockUser {
  id: string;
  email: string;
  user_metadata?: {
    full_name?: string;
  };
}

export interface MockSession {
  access_token: string;
  expires_at: number;
  user: MockUser;
}

interface StoredMockUser extends MockUser {
  password: string;
}

interface AuthResponse {
  data: {
    user: MockUser | null;
    session: MockSession | null;
  };
  error: { message: string } | null;
}

const USERS_STORAGE_KEY = "mock-auth-users";
const SESSION_STORAGE_KEY = "mock-auth-session";
export const AUTH_STATE_EVENT = "mock-auth-state-changed";

function readUsers(): StoredMockUser[] {
  const raw = window.localStorage.getItem(USERS_STORAGE_KEY);
  if (!raw) return [];

  try {
    return JSON.parse(raw) as StoredMockUser[];
  } catch {
    return [];
  }
}

function writeUsers(users: StoredMockUser[]) {
  window.localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(users));
}

function writeSession(session: MockSession | null) {
  if (session) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  window.dispatchEvent(new Event(AUTH_STATE_EVENT));
}

function buildSession(user: MockUser): MockSession {
  return {
    access_token: crypto.randomUUID(),
    expires_at: Date.now() + 1000 * 60 * 60 * 8,
    user,
  };
}

export function getCurrentSession(): MockSession | null {
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return null;

  try {
    const session = JSON.parse(raw) as MockSession;
    if (session.expires_at <= Date.now()) {
      writeSession(null);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export async function signInWithPassword({
  email,
  password,
}: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const users = readUsers();
  const normalizedEmail = email.trim().toLowerCase();
  const existing = users.find((u) => u.email.toLowerCase() === normalizedEmail);

  if (!existing || existing.password !== password) {
    return {
      data: { user: null, session: null },
      error: { message: "Email ou mot de passe invalide (mode mock)." },
    };
  }

  const user: MockUser = {
    id: existing.id,
    email: existing.email,
    user_metadata: { full_name: existing.user_metadata?.full_name || "" },
  };

  const session = buildSession(user);
  writeSession(session);

  return { data: { user, session }, error: null };
}

export async function signUp({
  email,
  password,
  options,
}: {
  email: string;
  password: string;
  options?: { data?: { full_name?: string } };
}): Promise<AuthResponse> {
  const users = readUsers();
  const normalizedEmail = email.trim().toLowerCase();

  if (users.some((u) => u.email.toLowerCase() === normalizedEmail)) {
    return {
      data: { user: null, session: null },
      error: { message: "Un compte existe deja pour cet email (mode mock)." },
    };
  }

  const newUser: StoredMockUser = {
    id: crypto.randomUUID(),
    email: normalizedEmail,
    password,
    user_metadata: {
      full_name: options?.data?.full_name || "",
    },
  };

  users.push(newUser);
  writeUsers(users);

  const user: MockUser = {
    id: newUser.id,
    email: newUser.email,
    user_metadata: { full_name: newUser.user_metadata?.full_name || "" },
  };

  const session = buildSession(user);
  writeSession(session);

  return { data: { user, session }, error: null };
}

export async function signOut(): Promise<void> {
  writeSession(null);
}

export async function updateProfile({
  userId,
  fullName,
}: {
  userId: string;
  fullName: string;
}): Promise<{ error: { message: string } | null }> {
  const users = readUsers();
  const userIndex = users.findIndex((u) => u.id === userId);

  if (userIndex < 0) {
    return { error: { message: "Utilisateur introuvable (mode mock)." } };
  }

  users[userIndex] = {
    ...users[userIndex],
    user_metadata: {
      ...(users[userIndex].user_metadata || {}),
      full_name: fullName,
    },
  };
  writeUsers(users);

  const currentSession = getCurrentSession();
  if (currentSession?.user.id === userId) {
    writeSession({
      ...currentSession,
      user: {
        ...currentSession.user,
        user_metadata: {
          ...(currentSession.user.user_metadata || {}),
          full_name: fullName,
        },
      },
    });
  }

  return { error: null };
}
