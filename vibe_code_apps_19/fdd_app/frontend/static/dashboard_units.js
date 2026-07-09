(function () {
  const KEY = "fdd-dashboard-units";
  const btn = document.getElementById("unit-toggle");
  if (!btn) return;

  function label(units) {
    return units === "metric" ? "°C / Metric" : "°F / Imperial";
  }

  function apply(units) {
    localStorage.setItem(KEY, units);
    btn.textContent = label(units);
    window.DASHBOARD_UNITS = units;
  }

  async function persist(units) {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ units }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error("Failed to save units");
  }

  const saved = localStorage.getItem(KEY) || "imperial";
  apply(saved === "metric" ? "metric" : "imperial");

  btn.addEventListener("click", async () => {
    const next = window.DASHBOARD_UNITS === "metric" ? "imperial" : "metric";
    apply(next);
    try {
      await persist(next);
      if (window.scheduleRefresh) window.scheduleRefresh();
      else location.reload();
    } catch (e) {
      alert(String(e.message || e));
    }
  });
})();
