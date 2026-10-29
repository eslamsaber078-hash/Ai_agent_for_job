import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/context/i18n";
import { api, ApiError, AUTH_EXPIRED_EVENT } from "@/lib/api";

export interface AuthUser {
  id: number;
  profile_id: number;
  phone: string;
  full_name: string;
}

interface Credentials {
  phone: string;
  password: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  retry: () => Promise<void>;
  login: (credentials: Credentials) => Promise<AuthUser>;
  register: (credentials: Credentials & { full_name: string }) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  const mutationPending = useRef(false);

  const retry = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    setWaking(false);
    const wakeTimer = window.setTimeout(() => setWaking(true), 3500);
    try {
      // Two retries: the first visit after a quiet spell is answered by a host that
      // is still booting, and "try again" from him at that moment only wastes time.
      const currentUser = await api.get<AuthUser>("/api/auth/me", { track: false, retries: 2 });
      if (version === requestVersion.current) setUser(currentUser);
    } catch (err) {
      if (version !== requestVersion.current) return;
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      } else {
        setError("We can't confirm your account right now. Check your connection, then try again.");
      }
    } finally {
      window.clearTimeout(wakeTimer);
      if (version === requestVersion.current) {
        setLoading(false);
        setWaking(false);
      }
    }
  }, []);

  useEffect(() => {
    const expire = () => {
      ++requestVersion.current;
      setUser(null);
      setLoading(false);
      setError(null);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, expire);
    void retry();
    return () => {
      ++requestVersion.current;
      window.removeEventListener(AUTH_EXPIRED_EVENT, expire);
    };
  }, [retry]);

  const authenticate = useCallback(async (path: string, credentials: Credentials & { full_name?: string }) => {
    if (mutationPending.current) throw new ApiError(409, "An authentication request is already in progress.");
    mutationPending.current = true;
    setBusy(true);
    try {
      const currentUser = await api.post<AuthUser>(path, credentials, { track: false });
      ++requestVersion.current;
      setUser(currentUser);
      setError(null);
      setLoading(false);
      return currentUser;
    } finally {
      mutationPending.current = false;
      setBusy(false);
    }
  }, []);

  const login = useCallback((credentials: Credentials) => authenticate("/api/auth/login", credentials), [authenticate]);
  const register = useCallback(
    (credentials: Credentials & { full_name: string }) => authenticate("/api/auth/register", credentials),
    [authenticate]
  );

  const logout = useCallback(async () => {
    if (mutationPending.current) throw new ApiError(409, "An authentication request is already in progress.");
    mutationPending.current = true;
    setBusy(true);
    try {
      const result = await api.post<{ ok: boolean }>("/api/auth/logout", undefined, { track: false });
      if (result.ok !== true) throw new ApiError(502, "The backend did not confirm logout.");
      ++requestVersion.current;
      setUser(null);
      setError(null);
    } finally {
      mutationPending.current = false;
      setBusy(false);
    }
  }, []);

  const { t } = useI18n();

  return (
    <AuthContext.Provider value={{ user, loading, error, busy, retry, login, register, logout }}>
      {loading || error ? (
        <main className="flex min-h-screen items-center justify-center bg-background p-4">
          <section className="w-full max-w-md rounded-xl border bg-card p-6 text-center shadow-sm" aria-busy={loading}>
            {loading ? (
              <div className="space-y-2" role="status" aria-live="polite">
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                  {waking ? t("Waking the server") : t("Checking your account…")}
                </div>
                {waking && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {t("The first visit after a quiet spell starts the server — it can take up to a minute.")}
                  </p>
                )}
              </div>
            ) : (
              <>
                <h1 className="mb-3 text-lg font-semibold">{t("Can't reach the server")}</h1>
                <p role="alert" className="mb-5 text-sm text-muted-foreground">{t(error ?? "")}</p>
                <Button onClick={() => void retry()}>{t("Try again")}</Button>
              </>
            )}
          </section>
        </main>
      ) : children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}

export function ProtectedRoute() {
  const { user } = useAuth();
  return user ? <Outlet key={user.profile_id} /> : <Navigate to="/login" replace />;
}
