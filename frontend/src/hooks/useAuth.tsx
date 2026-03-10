import { useEffect, useState } from "react";
import {
  AUTH_STATE_EVENT,
  type MockSession,
  type MockUser,
  getCurrentSession,
  signInWithPassword,
  signOut,
  signUp,
  updateProfile,
} from "../lib/mockAuth";

export function useAuth() {
  const [user, setUser] = useState<MockUser | null>(null);
  const [session, setSession] = useState<MockSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const refreshAuthState = () => {
      const session = getCurrentSession();
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    };

    refreshAuthState();

    window.addEventListener(AUTH_STATE_EVENT, refreshAuthState);
    window.addEventListener("storage", refreshAuthState);

    return () => {
      window.removeEventListener(AUTH_STATE_EVENT, refreshAuthState);
      window.removeEventListener("storage", refreshAuthState);
    };
  }, []);

  return { user, session, loading, signOut, signInWithPassword, signUp, updateProfile };
}
