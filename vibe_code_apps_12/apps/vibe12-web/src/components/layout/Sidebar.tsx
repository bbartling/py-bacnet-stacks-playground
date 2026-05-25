import { NavLink } from "react-router-dom";
import { useTheme } from "../../contexts/theme-context";
import { useAuth } from "../../contexts/auth-context";

const navItems = [
  { to: "/dashboard", icon: "📈", label: "Dashboard" },
  { to: "/sites", icon: "🏢", label: "Sites" },
  { to: "/explore", icon: "🔬", label: "Explore" },
  { to: "/edge-devices", icon: "📡", label: "Edge" },
  { to: "/rule-lab", icon: "🧩", label: "Rule Lab" },
  { to: "/data-model", icon: "🧱", label: "Data Model" },
  { to: "/system", icon: "🖥️", label: "System" },
];

export function Sidebar() {
  const { theme, setTheme } = useTheme();
  const { logout, username } = useAuth();

  return (
    <aside className="sidebar">
      <div className="brand-row">
        <span className="brand">Vibe12</span>
        <span className="brand-chip">Cloud</span>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span className="nav-icon" aria-hidden="true">
              {item.icon}
            </span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer muted">
        {username ? `Signed in as ${username}` : ""}
        <button type="button" className="secondary-btn sidebar-logout" onClick={logout}>
          Sign out
        </button>
      </div>
      <div className="theme-switcher">
        {(["light", "dark", "system"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`theme-btn ${theme === t ? "active" : ""}`}
            onClick={() => setTheme(t)}
          >
            {t === "system" ? "Auto" : t === "light" ? "Light" : "Dark"}
          </button>
        ))}
      </div>
    </aside>
  );
}
