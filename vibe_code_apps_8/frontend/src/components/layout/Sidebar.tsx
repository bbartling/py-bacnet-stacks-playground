import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  CircleDot,
  AlertTriangle,
  LineChart,
  Cpu,
  BookOpen,
  CalendarClock,
  Database,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/contexts/theme-context";
import { Sun, Moon } from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/live-points", label: "Live points", icon: CircleDot, end: false },
  { to: "/driver", label: "Driver configs", icon: Database, end: false },
  { to: "/trends", label: "Trends", icon: LineChart, end: false },
  { to: "/faults", label: "Faults", icon: AlertTriangle, end: false },
  { to: "/schedule", label: "Occupancy", icon: CalendarClock, end: false },
  { to: "/system", label: "System", icon: Cpu, end: false },
  { to: "/docs", label: "BACnet notes", icon: BookOpen, end: false },
] as const;

const THEME_OPTIONS = [
  { value: "light" as const, icon: Sun, label: "Light" },
  { value: "dark" as const, icon: Moon, label: "Dark" },
];

export function Sidebar() {
  const { theme, setTheme } = useTheme();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border/60 bg-card/50">
      <div className="flex items-center gap-2.5 border-border/60 px-5 py-4">
        <span className="text-lg font-semibold tracking-tight text-foreground">BAS Lite</span>
        <Badge variant="outline" className="text-[10px]">
          VOLTTRON
        </Badge>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150 ${
                isActive
                  ? "bg-muted/70 font-medium text-foreground"
                  : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
              }`
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border/60 px-5 py-3">
        <div className="flex items-center rounded-lg bg-muted/60 p-1">
          {THEME_OPTIONS.map(({ value, icon: Icon, label }) => {
            const isActive = theme === value || (theme === "system" && value === "light");
            return (
              <button
                key={value}
                type="button"
                aria-label={label}
                title={label}
                onClick={() => setTheme(value)}
                className={`flex flex-1 items-center justify-center rounded-md p-1.5 transition-colors duration-150 ${
                  isActive
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
