#!/usr/bin/env python
"""Generate lakeside_desktop_sim_playground.ipynb — ONNX hybrid walk like the Rust app."""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "lakeside_desktop_sim_playground.ipynb"


def _reindent_py(src: str, width: int = 4) -> str:
    lines = src.strip("\n").splitlines()
    out: list[str] = []
    level = 0
    stack_levels: list[int] = []

    def _is_dedent_kw(s: str) -> bool:
        return s.startswith(("except ", "except:", "elif ", "else:", "finally:"))

    for raw in lines:
        if not raw.strip():
            out.append("")
            continue
        stripped = raw.lstrip(" \t")
        orig_lead = len(raw) - len(raw.lstrip(" "))
        if _is_dedent_kw(stripped):
            if orig_lead == 0:
                level = 0
                stack_levels = []
            elif stack_levels:
                level = stack_levels.pop()
        elif orig_lead == 0:
            level = 0
            stack_levels = []
        out.append((" " * (width * level)) + stripped)
        code_part = stripped.split("#", 1)[0].rstrip()
        if code_part.endswith(":"):
            stack_levels.append(level)
            level += 1
    return "\n".join(out) + "\n"


def md(s: str):
    return nbf.v4.new_markdown_cell(s.strip() + "\n")


def code(s: str):
    return nbf.v4.new_code_cell(_reindent_py(s))


def code_raw(s: str):
    return nbf.v4.new_code_cell(s.strip("\n") + "\n")


def build() -> nbf.NotebookNode:
    cells = []
    cells.append(
        md(
            """
# Lakeside desktop sim playground

Same story as the **Rust desktop app**, in notebook cells:

1. Midnight facility kW + 6 zone temps  
2. 96-step OAT day  
3. Strategy → control schedule  
4. ONNX hybrid walk = **baseline + E+ delta**  
5. Peak / kWh / incremental demand  
6. 24/7 vs DSM overlay  
7. STRATEGY ENUMERATION table  

Needs `real_baseline_15min_v1.onnx` + `eplus_delta_15min_v1.onnx` under `ml/artifacts`
(or `desktop/artifacts` via promote). No training in this notebook.
"""
        )
    )
    cells.append(
        code(
            r"""
%matplotlib inline
from datetime import datetime
print("KERNEL ALIVE", datetime.now().isoformat(timespec="seconds"), flush=True)

import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ROOT = Path("..").resolve()
if not (ROOT / "ml").is_dir():
    ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_paths import artifact_paths
from notebook_plots import apply_notebook_theme, save_fig
from hybrid_rollout import (
    STEPS,
    HybridModels,
    load_hybrid_onnx,
    schedule_from_strategy_fixture,
    rollout_96,
)
from feature_compile_heating_dsm import STRATEGY_IDS, ZONE_TEMP_COLS
from simulation_contract import incremental_demand

apply_notebook_theme()
PATHS = artifact_paths()
OUT = PATHS["figures"].parent
FIG = PATHS["figures"]
FIG.mkdir(parents=True, exist_ok=True)
DESK = ROOT / "desktop" / "artifacts"

def _find(name: str) -> Path:
    for d in (OUT, DESK, Path(os.environ.get("LAKESIDE_ONNX_DIR", ""))):
        if not d or not str(d):
            continue
        p = Path(d) / name
        if p.is_file():
            return p
    raise FileNotFoundError(name)

base_onnx = _find("real_baseline_15min_v1.onnx")
delta_onnx = _find("eplus_delta_15min_v1.onnx")
models = load_hybrid_onnx(base_onnx, delta_onnx)
print("ONNX baseline", base_onnx)
print("ONNX delta", delta_onnx)
print("features", len(models.feature_cols))
print("SETUP COMPLETE", flush=True)
"""
        )
    )

    cells.append(md("## 1 · Midnight state (like the desktop sliders)"))
    cells.append(
        code(
            r"""
midnight_facility_kw = 45.0
midnight_zones_f = [62.0] * 6
oat_midnight_f = 15.0
existing_billing_peak_kw = 120.0
demand_rate_per_kw = 12.0
energy_rate_per_kwh = 0.08
print("midnight kW", midnight_facility_kw, "zones", midnight_zones_f)
print("billing peak to-date", existing_billing_peak_kw, "kW")
"""
        )
    )

    cells.append(md("## 2 · Weather day (96 × 15-min OAT)"))
    cells.append(
        code(
            r"""
# Synthetic cold weekday — same idea as desktop manual OAT grid
oat_24 = np.array([
    oat_midnight_f + 8.0 * np.sin((h - 14) * np.pi / 12.0)
    for h in range(24)
], dtype=float)
oat_96 = np.repeat(oat_24, 4)
rh_96 = np.full(STEPS, 55.0)
ghi_96 = np.array([200.0 if 8 <= (i // 4) < 17 else 0.0 for i in range(STEPS)])

fig, ax = plt.subplots(figsize=(9, 2.8))
ax.plot(np.arange(STEPS) / 4.0, oat_96, color="#457b9d", lw=1.8)
ax.set_xlabel("Hour"); ax.set_ylabel("OAT °F"); ax.set_title("Weather forecast (96 steps)")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
save_fig(FIG / "playground_oat.png", fig); plt.close(fig)
print("OAT min/max", float(oat_96.min()), float(oat_96.max()))
"""
        )
    )

    cells.append(md("## 3 · Strategy → ControlSchedule96"))
    cells.append(
        code(
            r"""
strategy_id = "stagger_preheat" if "stagger_preheat" in STRATEGY_IDS else STRATEGY_IDS[0]
baseline_id = "baseline" if "baseline" in STRATEGY_IDS else STRATEGY_IDS[0]
flat_id = "flat_24_7" if "flat_24_7" in STRATEGY_IDS else baseline_id

dsm_sched = schedule_from_strategy_fixture(strategy_id)
base_sched = schedule_from_strategy_fixture(baseline_id)
flat_sched = schedule_from_strategy_fixture(flat_id)
print("DSM strategy", strategy_id)
print("baseline", baseline_id, "| 24/7 counterfactual", flat_id)
print("available", list(STRATEGY_IDS))
"""
        )
    )

    cells.append(md("## 4 · ONNX hybrid walk (desktop Live Run)"))
    cells.append(
        code_raw(
            r'''
def make_contract(dsm_control: dict, *, strategy_label: str) -> dict:
    return {
        "contract_version": "hybrid_dsm_96_v1",
        "init": {
            "facility_kw": float(midnight_facility_kw),
            "oat_f": float(oat_96[0]),
            **{ZONE_TEMP_COLS[i]: float(midnight_zones_f[i]) for i in range(6)},
        },
        "weather_forecast_96": {
            "oat_f": [float(x) for x in oat_96],
            "rh_pct": [float(x) for x in rh_96],
            "ghi": [float(x) for x in ghi_96],
        },
        "baseline_control_96": base_sched,
        "dsm_control_96": dsm_control,
        "calendar": {
            "month": 1.0,
            "doy": 15.0,
            "is_weekend": 0.0,
            "occupied_schedule": [1.0 if 7 <= (s // 4) < 18 else 0.0 for s in range(STEPS)],
        },
        "comfort_htg_sp_f": 68.0,
        "comfort_band_f": 2.0,
        "strategy_id": strategy_label,
    }

walk_dsm = rollout_96(models, make_contract(dsm_sched, strategy_label=strategy_id))
walk_247 = rollout_96(models, make_contract(flat_sched, strategy_label=flat_id))

def series(walk, key="hybrid_facility_kw"):
    return np.array([float(s[key]) for s in walk["steps"][:STEPS]], dtype=float)

kw_dsm = series(walk_dsm)
kw_247 = series(walk_247)
kw_base = series(walk_dsm, "baseline_facility_kw")
print("DSM peak", float(kw_dsm.max()), "kWh", float(kw_dsm.sum() * 0.25))
print("24/7 peak", float(kw_247.max()), "kWh", float(kw_247.sum() * 0.25))
print("comfort violations DSM", walk_dsm["summary"].get("comfort_violations"))
'''
        )
    )

    cells.append(md("## 5 · Costs — energy + **incremental** demand (not full monthly)"))
    cells.append(
        code(
            r"""
def day_stats(kw: np.ndarray) -> dict:
    peak = float(kw.max())
    kwh = float(kw.sum() * 0.25)
    energy_cost = kwh * energy_rate_per_kwh
    new_p, inc_kw, inc_cost = incremental_demand(
        existing_billing_peak_kw, peak, demand_rate_per_kw
    )
    return {
        "peak_kw": peak,
        "kwh": kwh,
        "energy_$": energy_cost,
        "new_billing_peak": new_p,
        "inc_demand_kw": inc_kw,
        "inc_demand_$": inc_cost,
        "total_inc_$": energy_cost + inc_cost,
    }

stats = pd.DataFrame({
    "24/7 counterfactual": day_stats(kw_247),
    f"DSM ({strategy_id})": day_stats(kw_dsm),
}).T
display(stats.round(2))
display(Markdown(
    "Incremental demand = how much this day **raises** the billing-period peak. "
    "Days below the existing peak add **$0** demand."
))
"""
        )
    )

    cells.append(md("## 6 · Overlay — 24/7 vs DSM (one chart)"))
    cells.append(
        code(
            r"""
t = np.arange(STEPS) / 4.0
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.axvspan(5, 9, color="#f4a261", alpha=0.15, label="morning peak HE 05–09")
ax.plot(t, kw_247, color="#6c757d", lw=1.6, label="24/7 (diagnostic)")
ax.plot(t, kw_base, color="#457b9d", lw=1.4, ls="--", label="ML baseline arm")
ax.plot(t, kw_dsm, color="#e76f51", lw=2.0, label=f"DSM {strategy_id}")
ax.set_xlabel("Hour"); ax.set_ylabel("facility kW")
ax.set_title("Desktop-style Live Run — same midnight + weather")
ax.legend(frameon=False, fontsize=8)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
save_fig(FIG / "playground_247_vs_dsm.png", fig); plt.close(fig)
"""
        )
    )

    cells.append(
        md(
            """
## 7 · STRATEGY ENUMERATION (not optimization)

Same midnight + weather for every named desktop strategy. Reject comfort failures;
rank the rest by energy $ + incremental demand $.
"""
        )
    )
    cells.append(
        code_raw(
            r'''
rows = []
for sid in STRATEGY_IDS:
    if sid.startswith("prbs"):
        continue
    try:
        sched = schedule_from_strategy_fixture(sid)
        walk = rollout_96(models, make_contract(sched, strategy_label=sid))
        kw = series(walk)
        st = day_stats(kw)
        viol = int(walk["summary"].get("comfort_violations") or 0)
        feasible = viol == 0
        rows.append({
            "strategy": sid,
            "peak_kw": st["peak_kw"],
            "kwh": st["kwh"],
            "energy_$": st["energy_$"],
            "inc_dem_kw": st["inc_demand_kw"],
            "inc_dem_$": st["inc_demand_$"],
            "total_inc_$": st["total_inc_$"],
            "comfort_viol": viol,
            "feasible": feasible,
        })
    except Exception as e:
        rows.append({
            "strategy": sid,
            "peak_kw": np.nan,
            "kwh": np.nan,
            "energy_$": np.nan,
            "inc_dem_kw": np.nan,
            "inc_dem_$": np.nan,
            "total_inc_$": np.nan,
            "comfort_viol": -1,
            "feasible": False,
            "reject": str(e)[:80],
        })

enum_df = pd.DataFrame(rows)
enum_df = enum_df.sort_values(
    by=["feasible", "total_inc_$"],
    ascending=[False, True],
)
display(enum_df.round(2))
ok = enum_df[enum_df["feasible"] == True]
if len(ok):
    print("best feasible:", ok.iloc[0]["strategy"], "total_inc_$", round(float(ok.iloc[0]["total_inc_$"]), 2))
else:
    print("no feasible strategies under comfort band")
display(Markdown(
    "Annual rollup in the desktop remains **HEURISTIC** until Annual Replay exists."
))
'''
        )
    )

    nb = nbf.v4.new_notebook(
        cells=cells,
        metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
    )
    return nb


def main() -> None:
    NB.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(build(), NB)
    print("wrote", NB)


if __name__ == "__main__":
    main()
