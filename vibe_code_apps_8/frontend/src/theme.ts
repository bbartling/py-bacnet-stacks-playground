export type ThemePref = "light" | "dark";

const KEY = "theme";

export function readStoredTheme(): ThemePref | "system" | null {
  const t = localStorage.getItem(KEY);
  if (t === "light" || t === "dark" || t === "system") return t;
  return null;
}

export function applyThemeClass(pref: ThemePref): void {
  document.documentElement.classList.toggle("dark", pref === "dark");
}

export function setStoredTheme(pref: ThemePref): void {
  localStorage.setItem(KEY, pref);
  applyThemeClass(pref);
}

export function isDarkMode(): boolean {
  return document.documentElement.classList.contains("dark");
}

export function toggleLightDark(): void {
  setStoredTheme(isDarkMode() ? "light" : "dark");
}
