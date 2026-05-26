/** Plotly layout colors aligned with CSS `data-theme` variables. */

export type ResolvedTheme = "light" | "dark";

export type PlotlyThemeColors = {
  paper: string;
  plot: string;
  text: string;
  grid: string;
  primary: string;
  traceColors: string[];
};

const DARK_FALLBACK: PlotlyThemeColors = {
  paper: "#161b24",
  plot: "#161b24",
  text: "#e8edf6",
  grid: "#273043",
  primary: "#4f78e8",
  traceColors: ["#4f78e8", "#22c55e", "#f97316", "#a78bfa", "#14b8a6", "#f472b6", "#eab308", "#38bdf8"],
};

const LIGHT_FALLBACK: PlotlyThemeColors = {
  paper: "#ffffff",
  plot: "#ffffff",
  text: "#111827",
  grid: "#d8dfec",
  primary: "#2f57c7",
  traceColors: ["#2f57c7", "#15803d", "#c2410c", "#6d28d9", "#0f766e", "#be185d", "#a16207", "#0369a1"],
};

function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function plotlyThemeColors(resolved: ResolvedTheme): PlotlyThemeColors {
  const fb = resolved === "light" ? LIGHT_FALLBACK : DARK_FALLBACK;
  return {
    paper: cssVar("--panel", fb.paper),
    plot: cssVar("--panel", fb.plot),
    text: cssVar("--text", fb.text),
    grid: cssVar("--border", fb.grid),
    primary: cssVar("--primary", fb.primary),
    traceColors: fb.traceColors,
  };
}

export function plotlyBaseLayout(
  resolved: ResolvedTheme,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const c = plotlyThemeColors(resolved);
  return {
    paper_bgcolor: c.paper,
    plot_bgcolor: c.plot,
    font: { color: c.text, size: 12 },
    margin: { t: 24, r: 16, b: 48, l: 56 },
    xaxis: {
      title: "Time (UTC)",
      gridcolor: c.grid,
      linecolor: c.grid,
      tickfont: { color: c.text },
      titlefont: { color: c.text },
    },
    yaxis: {
      gridcolor: c.grid,
      linecolor: c.grid,
      tickfont: { color: c.text },
      titlefont: { color: c.text },
    },
    legend: { orientation: "h" as const, y: 1.12, font: { color: c.text } },
    ...overrides,
  };
}
