"""Generate notebooks/01_pid_hunt_tutorial.ipynb (controls-tech friendly)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path


def md(src: str) -> dict:
    lines = src.strip("\n").split("\n")
    return {
        "cell_type": "markdown",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": [ln + "\n" for ln in lines],
    }


def code(src: str) -> dict:
    lines = src.strip("\n").split("\n")
    return {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [ln + "\n" for ln in lines],
    }


cells = [
    md(
        """# Vibe 25 — Is this cooling valve hunting?

For **controls technicians**. We look at one analog output (cooling valve %) and ask:

> Is the valve settling, or is it swinging back and forth for a long time?

Open-FDD rule **PID-HUNT-1** is a screening tool. A flag means *suspected hunting* — not automatic proof that PID gains are wrong.

Helper code lives in Python modules under `vibe25/` (you import it; you do not need to read the math source)."""
    ),
    md(
        """## Install (once)

```text
pip install "open-fdd[oracle]" matplotlib
```

Or from this folder: `pip install -e ".[dev]"`"""
    ),
    code(
        """%pip install -q "open-fdd[oracle]>=4.4.1" matplotlib"""
    ),
    code(
        """from vibe25 import (
    fault_summary,
    healthy_cooling_valve,
    hunting_sine_cooling_valve,
    plot_healthy_vs_hunting,
    plot_valve_overview,
    plot_valve_zoom_with_tv,
    run_pid_hunt,
)
import matplotlib.pyplot as plt"""
    ),
    md(
        """## 1. What hunting looks like (synthetic trends)

Left: a **healthy** valve that slowly opens — the kind of trend you want after a load change.

Right: a **hunting** sine wave — the command keeps oscillating instead of settling."""
    ),
    code(
        """healthy = healthy_cooling_valve()
hunting = hunting_sine_cooling_valve()  # swinging sine wave

fig = plot_healthy_vs_hunting(healthy, hunting)
plt.show()"""
    ),
    md(
        """## 2. Full hunting trend

Same hunting sine, full length. Pink band = times Open-FDD would call **hunting** on a rolling 1-hour window."""
    ),
    code(
        """metrics = run_pid_hunt(hunting)
print(fault_summary(metrics))

fig = plot_valve_overview(hunting, metrics, title="Hunting cooling valve — full trend")
plt.show()"""
    ),
    md(
        """## 3. Zoom in — what is TV?

**Span** = high minus low on the wiggle (how tall the swing is).

**TV (total variation)** = add up *every* move (up and down), like an odometer for the valve command.

Open-FDD adds those moves over about **one hour**. If the valve travels too far, too often, it flags hunting.

The zoom below shows **3 cycles**. Blue arrows are individual moves. Those numbers **add up** to TV."""
    ),
    code(
        """fig = plot_valve_zoom_with_tv(
    hunting,
    start_sample=36,
    n_cycles=3,
    period_samples=6,
    title="Zoom: 3 hunting cycles — arrows add up to TV",
)
plt.show()"""
    ),
    md(
        """## 4. Healthy check (should stay clear)

Same detector on the slow ramp. You should see **no** hunting flag and a tiny TV."""
    ),
    code(
        """ok_metrics = run_pid_hunt(healthy)
print(fault_summary(ok_metrics))

fig = plot_valve_overview(healthy, ok_metrics, title="Healthy cooling valve — should not flag")
plt.show()"""
    ),
    md(
        """## Tech takeaways

| Word | Plain English |
|------|----------------|
| Valve % | Analog command / position (0–100) |
| Span | High − low of the swing |
| TV | Total travel (sum of ups and downs) |
| Hunting flag | Too much travel for too long (rolling ~1 hour) |

Use this on real historian data the same way: put valve % on a time index, call `run_pid_hunt(df)`.

Helper modules: `vibe25.synth`, `vibe25.detect`, `vibe25.plotting`."""
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
