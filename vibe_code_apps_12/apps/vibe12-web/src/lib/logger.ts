type Level = "debug" | "info" | "warn" | "error";

const LEVELS: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };

function threshold(): Level {
  const q =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("log")
      : null;
  const ls =
    typeof window !== "undefined" ? window.localStorage.getItem("vibe12_log") : null;
  const v = (q || ls || "info").toLowerCase();
  if (v === "debug" || v === "info" || v === "warn" || v === "error") return v;
  return "info";
}

let cached = threshold();

export function setLogLevel(level: Level) {
  cached = level;
  if (typeof window !== "undefined") {
    window.localStorage.setItem("vibe12_log", level);
  }
}

function emit(level: Level, scope: string, message: string, detail?: unknown) {
  if (LEVELS[level] < LEVELS[cached]) return;
  const prefix = `[vibe12][${scope}]`;
  const args: unknown[] = [prefix, message];
  if (detail !== undefined) args.push(detail);
  if (level === "error") console.error(...args);
  else if (level === "warn") console.warn(...args);
  else if (level === "debug") console.debug(...args);
  else console.info(...args);
}

export const logger = {
  debug: (scope: string, msg: string, detail?: unknown) => emit("debug", scope, msg, detail),
  info: (scope: string, msg: string, detail?: unknown) => emit("info", scope, msg, detail),
  warn: (scope: string, msg: string, detail?: unknown) => emit("warn", scope, msg, detail),
  error: (scope: string, msg: string, detail?: unknown) => emit("error", scope, msg, detail),
};
