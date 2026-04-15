import { Sun, Moon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "@/contexts/theme-context";
import { TutorialPopover } from "@/components/ui/tutorial-popover";
import { apiFetch } from "@/lib/bas-fetch";

export function TopBar() {
  const { theme, setTheme } = useTheme();
  const hostTime = useQuery({
    queryKey: ["bas-system-time"],
    queryFn: () => apiFetch<{ weekday: string; localDate: string; localTime: string }>("api/system/time"),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
  const isDark =
    theme === "dark" ||
    (theme === "system" && typeof document !== "undefined" && document.documentElement.classList.contains("dark"));

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border/60 bg-card/80 px-6 backdrop-blur-lg">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">BAS Lite: Open, Free, and Built for Makers</p>
        <p className="truncate text-xs text-muted-foreground">
          Discover fast, automate freely, and keep your building data in your hands
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">
          {hostTime.data ? `${hostTime.data.weekday} ${hostTime.data.localDate} ${hostTime.data.localTime}` : "Host time…"}
        </span>
        <TutorialPopover
          title="About this build"
          meaning="React + TypeScript SPA behind Caddy with realtime websocket + SSE updates."
          status="Runtime: Docker services (frontend, api, diy-bacnet, caddy) with high-frequency operator refresh."
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
