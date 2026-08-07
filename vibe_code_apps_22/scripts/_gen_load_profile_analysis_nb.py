#!/usr/bin/env python
"""Generate lakeside_load_profile_analysis.ipynb (site meter + Actual/E+/ML overlays)."""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "lakeside_load_profile_analysis.ipynb"


def _reindent_py(src: str, width: int = 4) -> str:
    """Repair collapsed 1-space nested blocks from historical generators."""
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
 """Already-correct 4-space Python (skip reindent heuristics)."""
 return nbf.v4.new_code_cell(s.strip("\n") + "\n")


def build() -> nbf.NotebookNode:
 cells = []
 cells.append(
 md(
 """
# Lakeside load-profile analysis - meter shapes + Actual vs E+ vs ML

Exploratory notebook for **typical electric demand shapes** at Lakeside ES and a
side-by-side overlay of **actual meter/BAS**, **EnergyPlus IdealLoads**, and
**ML hybrid predictions**.

| Claim | Value |
|---|---|
| Honesty | `HYBRID_SCREENING` / exploratory |
| Operational DSM | **Not approved** |
| Site | `$LAKESIDE_SITE_ROOT` (default Desktop `sp_creekside`) |

Hybrid ML traces are **counterfactual predictions** - never labeled as measured actual.
"""
 )
 )
 cells.append(
 code(
 r"""
%matplotlib inline
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display, Markdown, Image, HTML

ROOT = Path("..").resolve()
if not (ROOT / "ml").is_dir():
 ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT))

from lakeside.paths import site_root, clean_data_building_dir
from artifact_paths import artifact_paths
from notebook_plots import (
 save_fig,
 typical_weekday_weekend_profile,
 monthly_diurnal_overlay,
 actual_eplus_ml_overlay,
 winter_day_panel,
 apply_notebook_theme,
 metric_cards_html,
)

apply_notebook_theme()
SITE = Path(os.environ.get("LAKESIDE_SITE_ROOT", str(site_root())))
CLEAN = clean_data_building_dir()
METER = CLEAN / "CS_ELEC_METER" / "history_wide.csv"
PLOTS = SITE / "plots"
ANALYTICS = PLOTS / "analytics"
PATHS = artifact_paths()
OUT = PATHS["figures"].parent
FIG = PATHS["figures"]
FIG.mkdir(parents=True, exist_ok=True)

print("SITE", SITE, "exists", SITE.is_dir())
print("METER", METER, "exists", METER.is_file())
print("honesty HYBRID_SCREENING - exploratory load shapes only")
"""
 )
 )

 cells.append(md("## Inventory - site plots + meter"))
 cells.append(
 code(
 r"""
rows = []
for label, p in [
 ("site_root", SITE),
 ("meter_csv", METER),
 ("plots", PLOTS),
 ("plots/analytics", ANALYTICS),
 ("real_baseline_parquet", OUT / "real_baseline_15min_v1.parquet"),
 ("eplus_paired_parquet", OUT / "heating_dsm_eplus_paired_15min_v1.parquet"),
 ("hybrid_walk", OUT / "hybrid_dsm_96_v1_walk.json"),
]:
 rows.append({
 "name": label,
 "path": str(p),
 "exists": p.is_file() if p.suffix else p.is_dir(),
 })
display(pd.DataFrame(rows))

pngs = []
if PLOTS.is_dir():
 pngs = sorted(PLOTS.rglob("*.png"))[:40]
print(f"PNG files under plots/ (showing up to 40): {len(pngs)}")
for p in pngs[:15]:
 print(" ", p.relative_to(SITE) if SITE in p.parents or p.is_relative_to(SITE) else p)
"""
 )
 )

 cells.append(
 md(
 """
## Typical meter load shapes

Weekday vs weekend mean diurnal kW from `CS_ELEC_METER/history_wide.csv`.
If the CSV is missing (OneDrive not synced), this section skips with a clear message.
"""
 )
 )
 cells.append(
 code(
 r"""
demand = None
if not METER.is_file():
 display(Markdown(
 f"**Meter CSV missing** - tried `{METER}`. "
 "Hydrate OneDrive / run `scripts/process_lakeside.py` then re-open this notebook."
 ))
else:
 demand = pd.read_csv(METER)
 demand["timestamp_utc"] = pd.to_datetime(demand["timestamp_utc"], utc=True)
 demand = demand.sort_values("timestamp_utc").dropna(subset=["kw_demand"])
 demand["ts_local"] = demand["timestamp_utc"].dt.tz_convert("America/Chicago")
 demand["hour"] = demand["ts_local"].dt.hour
 demand["month"] = demand["ts_local"].dt.to_period("M").astype(str)
 demand["is_weekend"] = demand["ts_local"].dt.dayofweek >= 5
 demand["day_type"] = np.where(demand["is_weekend"], "Weekend", "Weekday")
 print("meter rows", len(demand), "span", demand["ts_local"].min(), "->", demand["ts_local"].max())

 fig, ax = plt.subplots(figsize=(9, 3.5))
 typical_weekday_weekend_profile(demand, ax=ax)
 save_fig(FIG / "analysis_typical_weekday_weekend.png", fig)
 plt.close(fig)

 fig = monthly_diurnal_overlay(demand)
 save_fig(FIG / "analysis_monthly_diurnal.png", fig)
 plt.close(fig)

 display(Markdown(
 "**Caption:** Weekday morning rise and weekend setback are the signatures a DSM "
 "surrogate must respect. Monthly panels show seasonality in the same shape family."
 ))
"""
 )
 )

 cells.append(md("## Existing analytics PNGs (site `plots/analytics`)"))
 cells.append(
 code(
 r"""
shown = 0
if ANALYTICS.is_dir():
 for p in sorted(ANALYTICS.glob("*.png"))[:8]:
 display(Markdown(f"### `{p.name}`"))
 try:
 display(Image(filename=str(p)))
 shown += 1
 except Exception as e:
 print("skip", p, e)
else:
 display(Markdown(f"No analytics dir at `{ANALYTICS}` - optional; meter charts above still apply."))
print("displayed", shown, "analytics PNGs")
"""
 )
 )

 cells.append(
 md(
 """
## Example winter day - BAS / ML frame

Uses the real-baseline training frame when available (15-min facility_kw + zones + OAT).
"""
 )
 )
 cells.append(
 code(
 r"""
bas_day = None
try:
 from train_real_baseline_15min import load_real_baseline_frame
 bas = load_real_baseline_frame(winter_only=True, max_days=36)
 days = sorted(bas["day"].astype(str).unique())
 bas_day = days[len(days) // 2]
 fig = winter_day_panel(bas, bas_day)
 save_fig(FIG / "analysis_bas_winter_day.png", fig)
 plt.close(fig)
 print("BAS example day", bas_day, "rows", (bas["day"].astype(str) == bas_day).sum())
except Exception as e:
 display(Markdown(f"BAS frame unavailable: `{e}`"))
"""
 )
 )

 cells.append(
 md(
 """
## Overlay - Actual vs EnergyPlus vs ML

When sources exist:

1. **Actual** - meter (hourly mean) or BAS `facility_kw` for a winter day 
2. **EnergyPlus** - paired farm baseline arm for a comparable day 
3. **ML** - hybrid walk JSON baseline + hybrid traces (predicted - **not actual**)

If a source is missing, the overlay still plots whatever is available and notes gaps.
"""
 )
 )
 cells.append(
 code_raw(
 r'''
hour = np.arange(24, dtype=float)
actual_kw = eplus_kw = ml_base = ml_hyb = None
notes = []

# --- Actual from meter (hourly mean of a cold-ish day) or BAS ---
if demand is not None and len(demand):
    dlocal = demand.copy()
    dlocal["day"] = dlocal["ts_local"].dt.strftime("%Y-%m-%d")
    winter = dlocal[dlocal["ts_local"].dt.month.isin([12, 1, 2]) & (~dlocal["is_weekend"])]
    pick = winter if len(winter) else dlocal
    day_counts = pick.groupby("day")["kw_demand"].count()
    day_pick = day_counts[day_counts >= 20].index
    if len(day_pick):
        d0 = str(sorted(day_pick)[len(day_pick) // 2])
        sub = dlocal[dlocal["day"] == d0]
        g = sub.groupby("hour")["kw_demand"].mean().reindex(range(24))
        actual_kw = g.values
        notes.append(f"actual meter day={d0}")
    else:
        notes.append("meter present but no usable day with >=20 intervals")
elif bas_day is not None:
    try:
        sub = bas[bas["day"].astype(str) == bas_day].sort_values(
            "step_15" if "step_15" in bas.columns else "hour_ending"
        )
        if "step_15" in sub.columns:
            kw = sub["facility_kw"].to_numpy()
            actual_kw = np.array([kw[i * 4 : (i + 1) * 4].mean() for i in range(24)])
        else:
            actual_kw = sub.groupby("hour_ending")["facility_kw"].mean().reindex(range(24)).values
        notes.append(f"actual from BAS frame day={bas_day}")
    except Exception as e:
        notes.append(f"BAS actual failed: {e}")
else:
    notes.append("no actual series")

# --- E+ paired baseline arm ---
paired = OUT / "heating_dsm_eplus_paired_15min_v1.parquet"
if paired.is_file():
    try:
        ep = pd.read_parquet(paired)
        if "control_regime" in ep.columns:
            ep_b = ep[ep["control_regime"].astype(str).str.contains("baseline", case=False, na=False)]
        elif "strategy_id" in ep.columns:
            ep_b = ep[ep["strategy_id"].astype(str) == "baseline"]
        else:
            ep_b = ep
        if "day" in ep_b.columns and "facility_kw" in ep_b.columns:
            edays = sorted(ep_b["day"].astype(str).unique())
            ed = edays[min(len(edays) // 2, len(edays) - 1)]
            esub = ep_b[ep_b["day"].astype(str) == ed].sort_values(
                "step_15" if "step_15" in ep_b.columns else "hour_ending"
            )
            if "step_15" in esub.columns and len(esub) >= 96:
                kw = esub["facility_kw"].to_numpy()[:96]
                eplus_kw = np.array([kw[i * 4 : (i + 1) * 4].mean() for i in range(24)])
            else:
                eplus_kw = esub.groupby("hour_ending")["facility_kw"].mean().reindex(range(24)).values
            notes.append(f"E+ baseline day={ed} (IdealLoads screening twin)")
        else:
            notes.append("E+ parquet missing day/facility_kw columns")
    except Exception as e:
        notes.append(f"E+ load failed: {e}")
else:
    notes.append(f"E+ paired parquet missing: {paired.name}")

# --- ML hybrid walk ---
walk_path = OUT / "hybrid_dsm_96_v1_walk.json"
if walk_path.is_file():
    try:
        walk = json.loads(walk_path.read_text(encoding="utf-8"))
        steps = walk.get("steps") or []
        if len(steps) >= 96:
            b = np.array([float(s["baseline_facility_kw"]) for s in steps[:96]])
            h = np.array([float(s["hybrid_facility_kw"]) for s in steps[:96]])
            ml_base = np.array([b[i * 4 : (i + 1) * 4].mean() for i in range(24)])
            ml_hyb = np.array([h[i * 4 : (i + 1) * 4].mean() for i in range(24)])
            notes.append(
                f"ML walk source={walk.get('source')} honesty={walk.get('honesty')} "
                f"(predicted baseline + hybrid - NOT measured actual)"
            )
    except Exception as e:
        notes.append(f"ML walk failed: {e}")
else:
    notes.append("hybrid walk JSON missing - run sklearn promote first")

display(Markdown("### Overlay notes\n- " + "\n- ".join(notes)))

fig, ax = plt.subplots(figsize=(10, 4))
actual_eplus_ml_overlay(
    hour=hour,
    actual_kw=actual_kw,
    eplus_kw=eplus_kw,
    ml_baseline_kw=ml_base,
    ml_hybrid_kw=ml_hyb,
    ax=ax,
)
save_fig(FIG / "analysis_actual_eplus_ml_overlay.png", fig)
plt.close(fig)

display(Markdown(
    "**Caption:** Compare morning-peak timing and magnitude across sources. "
    "E+ is an IdealLoads+COP screening twin; ML hybrid is a counterfactual prediction. "
    "Gaps in coverage (underpowered farm / smoke ship) mean this is **exploratory**, not a savings claim."
))
'''
 )
 )

 cells.append(
 md(
 """
## Interpretation checklist

- Weekday profiles should show a **morning heating ramp** (roughly HE 05-09).
- Weekend profiles are often flatter / lower - occupancy and setback.
- E+ IdealLoads will not match plant kW exactly; treat shape similarity as screening evidence.
- ML hybrid must never be read as a measured bill or field DSM outcome under `HYBRID_SCREENING`.

**Status:** RESEARCH / EXPLORATORY - not approved for operational DSM.
"""
 )
 )

 nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
 return nb


def main() -> None:
 NB.parent.mkdir(parents=True, exist_ok=True)
 nb = build()
 nbf.write(nb, NB)
 print("wrote", NB, "cells", len(nb.cells))


if __name__ == "__main__":
 main()
