async function refresh() {
  const res = await fetch("/points");
  const data = await res.json();
  const tbody = document.querySelector("#points tbody");
  tbody.innerHTML = "";
  for (const p of data.points) {
    const el = document.getElementById(p.name);
    if (el) {
      if (p.name === "FAN-S") el.textContent = p.present_value >= 0.5 ? "ON" : "OFF";
      else if (p.name === "MODE") {
        el.textContent = ["OFF", "HEAT", "COOL", "FAN"][Math.round(p.present_value)] || String(p.present_value);
      } else el.textContent = Number(p.present_value).toFixed(2);
    }
    const input = document.getElementById("in-" + p.name);
    if (input && document.activeElement !== input) {
      input.value = Number(p.present_value);
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${p.name}</td><td>${Number(p.present_value).toFixed(3)}</td><td>${p.winning_priority ?? "—"}</td><td>${p.winning_source ?? "—"}</td><td>${p.kind}</td>`;
    tbody.appendChild(tr);
  }
}

document.querySelectorAll("[data-write]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.getAttribute("data-write");
    const input = document.getElementById("in-" + name);
    const value = Number(input.value);
    await fetch(`/points/${name}/write`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, priority: 8, source: "ui" }),
    });
    await refresh();
  });
});

document.querySelectorAll("[data-rel]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.getAttribute("data-rel");
    await fetch(`/points/${name}/relinquish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ priority: 8 }),
    });
    await refresh();
  });
});

refresh();
setInterval(refresh, 1000);
