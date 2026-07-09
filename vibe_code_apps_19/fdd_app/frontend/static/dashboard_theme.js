(function () {
  const KEY = "fdd-dashboard-theme";
  const root = document.documentElement;

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "light" ? "Dark mode" : "Light mode";
  }

  const saved = localStorage.getItem(KEY);
  apply(saved === "light" ? "light" : "dark");

  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    apply(next);
    // Re-render server-side Plotly charts so their colors match the new theme.
    if (typeof window.scheduleRefresh === "function") window.scheduleRefresh();
  });
})();
