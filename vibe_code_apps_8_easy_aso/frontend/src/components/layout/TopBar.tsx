import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/contexts/theme-context";
import { TutorialPopover } from "@/components/ui/tutorial-popover";

export function TopBar() {
  const { theme, setTheme } = useTheme();
  const isDark =
    theme === "dark" ||
    (theme === "system" && typeof document !== "undefined" && document.documentElement.classList.contains("dark"));

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border/60 bg-card/80 px-6 backdrop-blur-lg">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">BMS / BAS Lite operator UI</p>
        <p className="truncate text-xs text-muted-foreground">
          Served by Docker (Caddy + nginx) with easy-aso FastAPI on this edge host
        </p>
      </div>
      <div className="flex items-center gap-2">
        <TutorialPopover
          title="About this build"
          meaning="React + TypeScript SPA behind Caddy. Legacy JSON under /app8/api/*; easy-aso REST under /api/v1/*."
          status="API is easy-aso (FastAPI). Legacy JSON stays under /app8/api/* for this SPA."
          side="bottom"
        >
          <span className="cursor-help text-xs text-muted-foreground">Help</span>
        </TutorialPopover>
        <button
          type="button"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
