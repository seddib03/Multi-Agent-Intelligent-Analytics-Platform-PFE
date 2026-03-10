import { useEffect, useState } from "react";
import {
  AUTH_STATE_EVENT,
  authDeleteMe,
  authGetMe,
  authUpdateMe,
  authUpdatePreferences,
  type MockSession,
  type MockUser,
  type BackendPreferences,
  type BackendUserProfile,
  ensureValidSession,
  getCurrentSession,
  signInWithPassword,
  signOut,
  signUp,
  updateProfile,
  usersDeleteMe,
  usersGetMe,
  usersUpdateMe,
  usersUpdatePreferences,
} from "../lib/mockAuth";

export function useAuth() {
  const [user, setUser] = useState<MockUser | null>(null);
  const [session, setSession] = useState<MockSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const refreshAuthState = async () => {
      const localSession = getCurrentSession();
      if (!cancelled) {
        setSession(localSession);
        setUser(localSession?.user ?? null);
      }

      const validSession = await ensureValidSession();
      if (!cancelled) {
        setSession(validSession);
        setUser(validSession?.user ?? null);
        setLoading(false);
      }
    };

    void refreshAuthState();

    window.addEventListener(AUTH_STATE_EVENT, refreshAuthState);
    window.addEventListener("storage", refreshAuthState);

    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_STATE_EVENT, refreshAuthState);
      window.removeEventListener("storage", refreshAuthState);
    };
  }, []);

  const updateMyPreferences = (payload: BackendPreferences) => usersUpdatePreferences(payload);

  return {
    user,
    session,
    loading,
    signOut,
    signInWithPassword,
    signUp,
    updateProfile,
    authGetMe,
    authUpdateMe,
    authDeleteMe,
    authUpdatePreferences,
    usersGetMe,
    usersUpdateMe,
    usersDeleteMe,
    usersUpdatePreferences,
    updateMyPreferences,
  } as {
    user: MockUser | null;
    session: MockSession | null;
    loading: boolean;
    signOut: typeof signOut;
    signInWithPassword: typeof signInWithPassword;
    signUp: typeof signUp;
    updateProfile: typeof updateProfile;
    authGetMe: typeof authGetMe;
    authUpdateMe: typeof authUpdateMe;
    authDeleteMe: typeof authDeleteMe;
    authUpdatePreferences: typeof authUpdatePreferences;
    usersGetMe: typeof usersGetMe;
    usersUpdateMe: typeof usersUpdateMe;
    usersDeleteMe: typeof usersDeleteMe;
    usersUpdatePreferences: typeof usersUpdatePreferences;
    updateMyPreferences: (payload: BackendPreferences) => Promise<{ error: { message: string } | null }>;
    _profileTypeHint?: BackendUserProfile;
  };
}
