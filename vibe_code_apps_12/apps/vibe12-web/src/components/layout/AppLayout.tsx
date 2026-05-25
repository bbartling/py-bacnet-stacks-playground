import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../contexts/auth-context";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const { ready, authenticated, authRequired } = useAuth();

  if (!ready) {
    return (
      <div className="login-shell">
        <p className="muted">Loading session…</p>
      </div>
    );
  }

  if (authRequired && !authenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <div className="status-strip">
          AWS IoT → DynamoDB · Lambda-hosted UI · consulting engineer access
        </div>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
