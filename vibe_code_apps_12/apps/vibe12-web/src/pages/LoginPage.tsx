import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/auth-context";
import { logger } from "../lib/logger";

export function LoginPage() {
  const { ready, authenticated, authRequired, login } = useAuth();
  const navigate = useNavigate();
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (ready && (!authRequired || authenticated)) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(user.trim(), pass);
      navigate("/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      logger.error("auth", "login failed", msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="card login-card">
        <h1 className="title">Vibe12 Cloud</h1>
        <p className="muted">Consulting engineer sign-in</p>
        <form className="login-form" onSubmit={(e) => void onSubmit(e)}>
          <label>
            Username
            <input
              autoComplete="username"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              required
            />
          </label>
          {error ? <p className="login-error">{error}</p> : null}
          <button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted small-hint">
          Set <code>VIBE12_WEB_USER</code> / <code>VIBE12_WEB_PASSWORD</code> on the Lambda. Debug logs:{" "}
          <code>?log=debug</code>
        </p>
      </div>
    </div>
  );
}
