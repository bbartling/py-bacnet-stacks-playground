#!/usr/bin/env python
"""Generate lakeside_load_profile_analysis.ipynb (meter analytics + clearer overlays)."""
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
# Lakeside load-profile analysis

Simple site look at **meter demand shapes**, **weather vs kW**, and **GL14 calibration
progress** — then a careful side-by-side of Actual / EnergyPlus / ML (often *different*
calendar days; compare shape, not lock-step magnitude).

Set `LAKESIDE_SITE_ROOT` if needed (default Desktop `sp_creekside`).
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
from IPython.display import display, Markdown, Image

ROOT = Path("..").resolve()
if not (ROOT / "ml").is_dir():
    ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from lakeside.paths import site_root, clean_data_building_dir
from artifact_paths import artifact_paths
from notebook_plots import save_fig, winter_day_panel, apply_notebook_theme

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
print("ANALYTICS", ANALYTICS)
"""
        )
    )

    cells.append(md("## Inventory"))
    cells.append(
        code(
            r"""
rows = []
for label, p in [
    ("site_root", SITE),
    ("meter_csv", METER),
    ("plots/analytics", ANALYTICS),
    ("weather_csv", CLEAN / "weather" / "history_wide.csv"),
    ("gl14_campaign_log", SITE / "eplus" / "scorecards" / "campaign_log.csv"),
    ("hybrid_walk", OUT / "hybrid_dsm_96_v1_walk.json"),
]:
    rows.append({
        "name": label,
        "path": str(p),
        "exists": p.is_file() if p.suffix else p.is_dir(),
    })
display(pd.DataFrame(rows))
"""
        )
    )

    cells.append(
        md(
            """
## Site analytics charts (regenerated here)

Runs the same Python that built `plots/analytics/*.png` — meter weekday/weekend,
demand vs Open-Meteo weather, and GL14 iteration charts. No duplicate hand-rolled
diurnal section above this.
"""
        )
    )
    cells.append(
        code_raw(
            r'''
from demand_weather_charts import regenerate_analytics_charts

ALLOW_WEATHER_FETCH = os.environ.get("VIBE22_ALLOW_WEATHER_FETCH", "0") == "1"
written = regenerate_analytics_charts(allow_weather_fetch=ALLOW_WEATHER_FETCH)
print("wrote/refreshed", len(written), "charts")

WANT = [
    "demand_weekday_weekend_summary.png",
    "demand_monthly_weekday_weekend_profiles.png",
    "demand_vs_web_weather_scatter.png",
    "demand_vs_web_weather_density.png",
    "demand_vs_web_weather_scatter_peak_day.png",
    "gl14_progress_by_iteration.png",
    "gl14_status_by_iteration.png",
    "monthly_error_heatmap.png",
]

shown = 0
for name in WANT:
    p = ANALYTICS / name
    display(Markdown(f"### `{name}`"))
    if p.is_file():
        try:
            display(Image(filename=str(p)))
            shown += 1
        except Exception as e:
            print("display failed", p, e)
    else:
        display(Markdown(
            f"*Missing `{p}` — meter/weather/GL14 inputs may be absent. "
            f"Set `VIBE22_ALLOW_WEATHER_FETCH=1` to pull Open-Meteo if weather CSV is missing.*"
        ))
print("displayed", shown, "/", len(WANT))
'''
        )
    )

    cells.append(
        md(
            """
## Example winter day (BAS frame)

One cold-season day from the real-baseline training store — facility kW + zones + OAT.
"""
        )
    )
    cells.append(
        code(
            r"""
bas_day = None
bas = None
try:
    from train_real_baseline_15min import load_real_baseline_frame
    from training_profile import require_profile
    prof = require_profile(os.environ.get("VIBE22_TRAINING_PROFILE", "smoke"))
    bas = load_real_baseline_frame(winter_only=True, max_days=prof.max_days, profile=prof)
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
## Shape gallery — peak demand day (+ E+ weather match)

Uses the **exact same peak day** as `demand_vs_web_weather_scatter_peak_day.png`
(local calendar day of max 5-min meter kW).

- **Actual / ML** — that calendar day  
- **EnergyPlus** — same day if farmed; otherwise **best OAT-matched** baseline farm day
  (labeled with OAT RMSE — a shape proxy, not a silent day swap)
"""
        )
    )
    cells.append(
        code_raw(
            r'''
import sys
sys.modules.pop("peak_day_shape_gallery", None)
from peak_day_shape_gallery import build_peak_day_gallery

# Prefer full BAS coverage so the peak day is present for ONNX init/weather
bas_full = None
try:
    from train_real_baseline_15min import load_real_baseline_frame
    bas_full = load_real_baseline_frame(winter_only=False, max_days=None)
except Exception as e:
    print("BAS full load skipped:", e)
    bas_full = bas  # fall back to earlier smoke/profile frame if any

gallery = build_peak_day_gallery(
    meter_csv=METER,
    paired_parquet=OUT / "heating_dsm_eplus_paired_15min_v1.parquet",
    artifacts_dir=OUT,
    bas=bas_full,
    strategy_id="stagger_preheat",
    weather_csv=CLEAN / "weather" / "history_wide.csv",
    allow_eplus_weather_match=True,
)

hour = np.arange(24, dtype=float)
actual_kw = gallery.actual_kw
eplus_kw = gallery.eplus_kw
ml_base = gallery.ml_baseline_kw
ml_hyb = gallery.ml_hybrid_kw
labels = gallery.labels

display(Markdown("### Notes\n- " + "\n- ".join(gallery.notes)))

fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.6), sharey=True)
panels = [
    (axes[0], actual_kw, None, labels["actual"], "1 · Actual meter", "#264653"),
    (axes[1], eplus_kw, None, labels["eplus"], "2 · EnergyPlus baseline", "#457b9d"),
    (axes[2], ml_base, ml_hyb, labels["ml"], "3 · ML ONNX (baseline + DSM)", "#e76f51"),
]
eplus_is_proxy = "weather-match" in str(labels.get("eplus", ""))
for ax, a, b, lab, title, color in panels:
    ax.axvspan(5, 9, color="#f4a261", alpha=0.15)
    ls = "--" if (ax is axes[1] and eplus_is_proxy) else "-"
    if a is not None and np.isfinite(a).any():
        ax.plot(
            hour,
            a,
            color=color,
            lw=2.0,
            ls=ls,
            label=("OAT proxy" if ls == "--" else "series") if b is None else "baseline",
        )
    if b is not None and np.isfinite(b).any():
        ax.plot(hour, b, color="#2a9d8f", lw=2.0, label="hybrid DSM")
    ax.set_title(f"{title}\n{lab}", fontsize=9)
    ax.set_xlabel("Hour")
    ax.set_xlim(0, 23)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if a is None or not np.isfinite(np.asarray(a, dtype=float)).any():
        ax.text(0.5, 0.5, "no data\nfor peak day", ha="center", va="center",
                transform=ax.transAxes, color="#888", fontsize=10)
    else:
        ax.legend(frameon=False, fontsize=8)
axes[0].set_ylabel("kW")
fig.suptitle(
    f"Peak demand day {gallery.peak_day} · max 5-min {gallery.peak_kw:.0f} kW · HE 05–09 band",
    fontsize=12,
    y=1.02,
)
fig.tight_layout()
save_fig(FIG / "analysis_shape_gallery_peak_day.png", fig)
plt.close(fig)

display(Markdown(
    f"- **Peak day:** `{gallery.peak_day}` at `{gallery.peak_ts_local}` ({gallery.peak_kw:.1f} kW)\n"
    f"- Actual: **{labels['actual']}**\n"
    f"- EnergyPlus: **{labels['eplus']}**\n"
    f"- ML: **{labels['ml']}**\n"
))
'''
        )
    )

    cells.append(
        md(
            """
## Quick read

- Gallery anchor is the **meter peak day** (same as the peak-day weather scatter).
- If E+ has no farm day for that date, the middle panel uses the **best OAT-matched** IdealLoads day (dashed = proxy).
- ML panel is a live ONNX hybrid walk for the peak calendar day.
"""
        )
    )

    nb = nbf.v4.new_notebook(
        cells=cells,
        metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
    )
    return nb


def main() -> None:
    NB.parent.mkdir(parents=True, exist_ok=True)
    nb = build()
    nbf.write(nb, NB)
    print("wrote", NB, "cells", len(nb.cells))


if __name__ == "__main__":
    main()
