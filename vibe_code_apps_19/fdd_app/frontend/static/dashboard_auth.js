(function () {
  const loginBtn = document.getElementById("btn-engineer-login");
  const logoutBtn = document.getElementById("btn-engineer-logout");
  const pinEl = document.getElementById("engineer-pin");
  const chip = document.getElementById("auth-chip");

  async function refreshSession() {
    const res = await fetch("/api/session");
    const data = await res.json();
    window.DASHBOARD_SESSION = data;
    document.body.classList.toggle("read-only-mode", !data.can_edit);
    const banner = document.getElementById("readonly-banner");
    if (banner) {
      banner.hidden = data.can_edit;
      banner.textContent = data.locked
        ? "Package locked — engineer login required to modify charts and settings."
        : "";
    }
    if (chip) {
      chip.dataset.engineer = data.engineer ? "1" : "0";
      if (loginBtn) loginBtn.hidden = data.engineer;
      if (logoutBtn) logoutBtn.hidden = !data.engineer;
      if (pinEl) pinEl.hidden = data.engineer;
    }
    document.querySelectorAll(".analyst-actions button, .site-settings-form button").forEach((btn) => {
      if (btn.id === "btn-engineer-login" || btn.id === "btn-engineer-logout") return;
      btn.disabled = !data.can_edit;
    });
    return data;
  }

  loginBtn?.addEventListener("click", async () => {
    const pin = pinEl ? pinEl.value : "";
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert("Invalid PIN");
      return;
    }
    await refreshSession();
  });

  logoutBtn?.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    await refreshSession();
  });

  refreshSession().catch(() => {});
})();
