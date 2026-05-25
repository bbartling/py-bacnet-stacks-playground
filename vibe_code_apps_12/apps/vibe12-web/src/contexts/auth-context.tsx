import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchMe, getToken, login as apiLogin, setToken } from "../lib/api-client";
import { logger } from "../lib/logger";

type AuthContextValue = {
  ready: boolean;
  authenticated: boolean;
  username: string;
  authRequired: boolean;
  login: (user: string, pass: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [authRequired, setAuthRequired] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setAuthRequired(me.auth_required);
      setUsername(me.username || "");
      setAuthenticated(!me.auth_required || Boolean(getToken()) || me.ok);
      logger.info("auth", "session ok", { user: me.username, required: me.auth_required });
    } catch (err) {
      setAuthenticated(false);
      setUsername("");
      logger.warn("auth", "session check failed", err);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (user: string, pass: string) => {
    const res = await apiLogin(user, pass);
    setUsername(res.username);
    setAuthenticated(true);
    setAuthRequired(res.auth_required);
    logger.info("auth", "logged in", { user: res.username });
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setAuthenticated(false);
    setUsername("");
    logger.info("auth", "logged out");
  }, []);

  const value = useMemo(
    () => ({ ready, authenticated, username, authRequired, login, logout }),
    [ready, authenticated, username, authRequired, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
