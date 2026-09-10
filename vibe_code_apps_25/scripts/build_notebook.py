"""Generate notebooks/01_pid_hunt_tutorial.ipynb (run once during scaffolding)."""
from __future__ import annotations

import json
from pathlib import Path


def md(src: str) -> dict:
    lines = src.strip("\n").split("\n")
    return {"cell_type": "markdown", "metadata": {}, "source": [ln + "\n" for ln in lines]}


def code(src: str) -> dict:
    lines = src.strip("\n").split("\n")
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [ln + "\n" for ln in lines],
    }


cells = [
    md(
        """# Vibe 25 — Open-FDD PID-HUNT-1 tutorial

Educational walkthrough of **suspected control-output hunting** using the pandas detector from PyPI package [`open-fdd`](https://pypi.org/project/open-fdd/).

**Claim:** screening demo only. A trip means the AO *looks like* hunting over a rolling hour — not proof that PID gains alone are wrong.

**Not in scope:** cookbook **FC4** (AHU operating-state / mode thrash). Same colloquial "PID hunting" name, different evidence."""
    ),
    md(
        """## 0. Install Open-FDD (oracle / pandas rules)

PyPI name is `open-fdd`; import path is `open_fdd`. Extra `[oracle]` installs the pandas rule stack."""
    ),
    code(
        """%pip install -q "open-fdd[oracle]>=4.4.1" matplotlib
# Optional tip-of-tree: %pip install -q -e "C:/Users/ben/Documents/open-fdd[oracle]" """
    ),
    code(
        """from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from open_fdd.rules.pid_hunting import PidHuntingParams, hunting_fault_mask

from vibe25.synth import COLUMN, POLL_SECONDS, healthy_cooling_valve, hunting_cooling_valve

params = PidHuntingParams()
params"""
    ),
    md(
        """## 1. Synthetic data — healthy vs hunting

We synthesize a `cooling-valve` AO (%) on a 1-minute `DatetimeIndex` (>=3 h so rolling 1 h windows fill).

- **Healthy:** slow ramp + sub-deadband noise (should stay clear)
- **Hunting:** 10 to 90 percent square chatter (should trip defaults)"""
    ),
    code(
        """healthy = healthy_cooling_valve()
hunting = hunting_cooling_valve()
healthy.head(), hunting[COLUMN].describe()"""
    ),
    md(
        """## 2. How the math works (PID-HUNT-1)

Open-FDD `hunting_fault_mask` (defaults from `PidHuntingParams`):

1. **Normalize** the command to 0-100% (`to_percent_output`).
2. Take sample-to-sample delta; ignore moves smaller than **`change_deadband_pct = 1`**.
3. Over a rolling **`window = 1h`**, compute:
   - **TV** (total variation) = sum of abs(significant delta) -> trip if >= **500** percent-points
   - **span** = rolling max - min -> trip if >= **20** %
   - **equivalent cycles** = TV / (2 * span) -> trip if >= **2.5**
   - **reversals** = sign flips of significant delta -> trip if >= **4**
   - **coverage** >= **80%** of expected samples in the window
4. **Fault** = AND of coverage, span, TV, cycles, reversals (and optional `loop-enabled`).

`low_extreme_seen` / `high_extreme_seen` are logged for diagnostics but are **not** part of the fault AND.

```text
fault = coverage>=80% AND span>=20% AND TV>=500 AND cycles>=2.5 AND reversals>=4
```

**FC4 != PID-HUNT-1:** FC4 counts AHU *operating-state* entry transitions per hour. PID-HUNT-1 watches analog AO travel."""
    ),
    code(
        """def run_hunt(df: pd.DataFrame):
    fault, metrics = hunting_fault_mask(
        df[COLUMN],
        params=params,
        poll_seconds=POLL_SECONDS,
    )
    out = metrics.copy()
    out["fault"] = fault.astype(bool)
    return out

m_hunt = run_hunt(hunting)
m_ok = run_hunt(healthy)
print("hunting fault samples:", int(m_hunt["fault"].sum()))
print("healthy fault samples:", int(m_ok["fault"].sum()))
peak = m_hunt.loc[m_hunt["fault"]].iloc[-1]
peak[
    [
        "control-output-pct",
        "total_variation_1h",
        "output_span_1h",
        "equivalent_cycles_1h",
        "reversals_1h",
        "coverage_pct_1h",
    ]
]"""
    ),
    md(
        """## 3. Schematic viz — AO vs time, then TV vs span (the AND gates)

Panel A shows the raw AO with fault shading. Panel B plots rolling **TV** against **span** (and marks thresholds) so you can see the quantities that combine into the fault."""
    ),
    code(
        """def plot_hunt(metrics: pd.DataFrame, title: str):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    ax0, ax1 = axes
    ao = metrics["control-output-pct"]
    fault = metrics["fault"].fillna(False)
    ax0.plot(ao.index, ao.values, color="#0d9b8c", lw=1.2, label="cooling-valve %")
    ax0.fill_between(ao.index, 0, 100, where=fault.values, color="#f87171", alpha=0.25, label="fault")
    ax0.set_ylabel("AO %")
    ax0.set_ylim(0, 100)
    ax0.set_title(title)
    ax0.legend(loc="upper right", fontsize=9)
    ax0.grid(True, alpha=0.3)

    ax1.plot(metrics.index, metrics["total_variation_1h"], color="#2563eb", lw=1.2, label="TV 1h")
    ax1.axhline(params.total_variation_fault_pct, color="#2563eb", ls="--", lw=1, label="TV>=500")
    ax1b = ax1.twinx()
    ax1b.plot(metrics.index, metrics["output_span_1h"], color="#c47b08", lw=1.2, label="span 1h")
    ax1b.axhline(params.minimum_span_pct, color="#c47b08", ls="--", lw=1, label="span>=20")
    ax1.set_ylabel("TV (percent-points)")
    ax1b.set_ylabel("span (%)")
    ax1.set_xlabel("time")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1b.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    return fig

fig = plot_hunt(m_hunt, "Hunting AO — PID-HUNT-1 trip region")
plt.show()

gates = pd.DataFrame(
    {
        "metric": ["coverage %", "span %", "TV percent-pts", "equiv cycles", "reversals"],
        "value": [
            float(peak["coverage_pct_1h"]),
            float(peak["output_span_1h"]),
            float(peak["total_variation_1h"]),
            float(peak["equivalent_cycles_1h"]),
            float(peak["reversals_1h"]),
        ],
        "threshold": [
            params.minimum_coverage_pct,
            params.minimum_span_pct,
            params.total_variation_fault_pct,
            params.minimum_equivalent_cycles,
            params.minimum_reversals,
        ],
    }
)
gates["passes"] = gates["value"] >= gates["threshold"]
gates"""
    ),
    code(
        """fig, ax = plt.subplots(figsize=(8, 3.5), constrained_layout=True)
colors = ["#4ade80" if p else "#f87171" for p in gates["passes"]]
ax.barh(gates["metric"], gates["value"], color=colors, alpha=0.85)
for i, row in gates.iterrows():
    ax.axvline(row["threshold"], color="#64748b", ls=":", lw=1)
    ax.text(row["threshold"], i, f"  thr={row['threshold']:g}", va="center", fontsize=8, color="#334155")
ax.set_xlabel("metric value at a peak fault sample")
ax.set_title("AND-gate schematic — all green bars must clear their thresholds")
ax.grid(True, axis="x", alpha=0.3)
plt.show()"""
    ),
    md(
        """## 4. Healthy contrast

Same detector, slow ramp — TV stays near zero under the 1% deadband, so the AND never closes."""
    ),
    code(
        """fig = plot_hunt(m_ok, "Healthy AO — no PID-HUNT-1 trip")
plt.show()
m_ok[
    [
        "control-output-pct",
        "total_variation_1h",
        "output_span_1h",
        "equivalent_cycles_1h",
        "reversals_1h",
        "fault",
    ]
].tail(3)"""
    ),
    md(
        """## Takeaways

- **TV** accumulates travel; **span** needs meaningful travel range; **cycles** = TV/(2*span); **reversals** need direction chatter.
- All must fire together with enough **coverage** — that is the fault.
- Use `open_fdd.rules.pid_hunting.hunting_fault_mask` (or cookbook `run_rule("PID-HUNT-1", ...)`) on real historian AOs the same way.
- For mode thrashing, look at **FC4**, not PID-HUNT-1."""
    ),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "cells": cells,
}

path = Path(__file__).resolve().parents[1] / "notebooks" / "01_pid_hunt_tutorial.ipynb"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8")
print("wrote", path, "cells", len(cells))
