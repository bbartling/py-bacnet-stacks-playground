#!/usr/bin/env python
"""Generate slim sklearn/torch *results viewer* notebooks (no training in-kernel).

Training SoT::

    python scripts/train_four_arms.py --profile full_evaluation

Notebooks only load ``ml/artifacts/runs/*/`` cards + timing.json.
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"


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


SETUP = r'''
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
from notebook_plots import apply_notebook_theme, save_fig, metric_cards_html
from timing_utils import format_hms

apply_notebook_theme()
PATHS = artifact_paths()
OUT = PATHS["figures"].parent
FIG = PATHS["figures"]
FIG.mkdir(parents=True, exist_ok=True)
RUNS = OUT / "runs"
INDEX = RUNS / "index.json"

print("ROOT", ROOT)
print("RUNS", RUNS, "exists", RUNS.is_dir())
print("INDEX", INDEX, "exists", INDEX.is_file())
if not INDEX.is_file():
    display(Markdown(
        "**No `runs/index.json` yet.** Train outside Jupyter:\n\n"
        "```powershell\n"
        "cd vibe_code_apps_22\n"
        "$env:VIBE22_ALLOW_CLI_TRAIN='1'\n"
        "python scripts/train_four_arms.py --profile full_evaluation\n"
        "# fast debug: python scripts/train_four_arms.py --profile smoke\n"
        "```\n"
    ))
print("SETUP COMPLETE", flush=True)
'''


LOAD_RUNS = r'''
def _read_json(p: Path):
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

index = _read_json(INDEX) or {"results": [], "note": "missing index — run train_four_arms.py"}
rows = []
for arm_dir in sorted(RUNS.glob("*")):
    if not arm_dir.is_dir():
        continue
    arm = arm_dir.name
    timing = _read_json(arm_dir / "timing.json") or {}
    result = _read_json(arm_dir / "result.json") or {}
    # pick card by family
    if arm.startswith("sklearn"):
        card_path = arm_dir / "real_baseline_15min_v1_model_card.json"
    else:
        card_path = arm_dir / "real_baseline_15min_torch_v1_model_card.json"
    card = _read_json(card_path) or {}
    tf = card.get("cv_teacher_forced") or {}
    rec = card.get("cv_recursive_96_heldout") or {}
    champ = card.get("champion") or card.get("family")
    if isinstance(rec, dict) and champ in rec and isinstance(rec[champ], dict):
        rec_block = rec[champ]
    else:
        rec_block = rec if isinstance(rec, dict) else {}
    rows.append({
        "arm": arm,
        "ok": result.get("ok"),
        "winter_only": timing.get("winter_only", result.get("winter_only")),
        "n_days": timing.get("n_days", result.get("n_days")),
        "train_hms": timing.get("total_hms") or result.get("timing_hms") or result.get("wall_hms"),
        "train_s": timing.get("total_seconds") or result.get("wall_seconds"),
        "champion": champ,
        "peak_mae_kw": rec_block.get("facility_kw_mae_peak_05_09") or tf.get("facility_kw_mae_peak_05_09"),
        "zone_mae_f": rec_block.get("zone_temp_mae_mean") or tf.get("zone_temp_mae_mean"),
        "card": str(card_path) if card_path.is_file() else None,
        "timing_file": str(arm_dir / "timing.json") if (arm_dir / "timing.json").is_file() else None,
    })

summary = pd.DataFrame(rows)
if summary.empty:
    display(Markdown("No arm folders under `ml/artifacts/runs/` yet."))
else:
    display(Markdown("### Train arms — wall clock + key metrics"))
    display(summary)
    display(Markdown(
        f"Launcher wall (all arms): **{format_hms(index.get('wall_seconds'))}** · "
        f"ok={index.get('ok_count')} fail={index.get('fail_count')}"
    ))
'''


TIMING_BARS = r'''
if not summary.empty and summary["train_s"].notna().any():
    plot_df = summary.dropna(subset=["train_s"]).sort_values("arm")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    colors = ["#264653" if w else "#e76f51" for w in plot_df["winter_only"].fillna(False)]
    ax.barh(plot_df["arm"], plot_df["train_s"], color=colors)
    ax.set_xlabel("Train wall seconds")
    ax.set_title("Train time by arm (winter=dark, allyear=orange)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_fig(FIG / "runs_train_times.png", fig)
    plt.close(fig)
else:
    display(Markdown("No timing seconds to plot yet."))
'''


DETAIL = r'''
# Per-arm timing breakdown
for arm in summary["arm"].tolist() if not summary.empty else []:
    tpath = RUNS / arm / "timing.json"
    timing = _read_json(tpath)
    if not timing:
        continue
    display(Markdown(f"#### `{arm}` — {timing.get('total_hms', 'n/a')}"))
    ents = timing.get("entries") or []
    if ents:
        display(pd.DataFrame(ents))
    else:
        print("(no step timings)")
'''


METRICS = r'''
# Side-by-side metric cards for winter vs allyear within this notebook's family
family = FAMILY  # set per notebook
sub = summary[summary["arm"].str.startswith(family)] if not summary.empty else summary
if sub.empty:
    display(Markdown(f"No `{family}_*` arms found."))
else:
    cards = []
    for _, r in sub.iterrows():
        cards.append({
            "label": r["arm"],
            "value": f"{r['peak_mae_kw']:.2f}" if pd.notna(r["peak_mae_kw"]) else "n/a",
            "unit": "kW peak MAE",
            "hint": f"zone {r['zone_mae_f']:.2f}°F · {r['train_hms']}" if pd.notna(r.get("zone_mae_f")) else str(r["train_hms"]),
        })
    display(HTML(metric_cards_html(cards, title=f"{family} arms")))
    display(sub[["arm", "winter_only", "n_days", "champion", "peak_mae_kw", "zone_mae_f", "train_hms"]])
'''


def build_sklearn() -> nbf.NotebookNode:
    cells = [
        md(
            """
# Lakeside sklearn — results viewer

**Training does not run in this notebook** (avoids dead Jupyter kernels).

```powershell
cd vibe_code_apps_22
$env:VIBE22_ALLOW_CLI_TRAIN="1"
python scripts/train_four_arms.py --profile full_evaluation
```

Arms: `sklearn_winter`, `sklearn_allyear`, `torch_winter`, `torch_allyear`  
Artifacts: `ml/artifacts/runs/<arm>/`
"""
        ),
        code(SETUP),
        md("## Load run index + cards"),
        code_raw(LOAD_RUNS),
        md("## Train times"),
        code_raw(TIMING_BARS),
        code_raw(DETAIL),
        md("## Sklearn metrics (winter vs all-year)"),
        code_raw("FAMILY = 'sklearn'\nfrom IPython.display import HTML\n" + METRICS),
        md(
            """
## Notes

- Winter = months Nov–Mar; all-year = no month filter (still subject to `--max-days` / profile).
- Peak MAE is recursive held-out when present, else teacher-forced.
- Desktop ship promote remains a separate step (`promote_hybrid_ship.py`) — not part of the four-arm matrix.
"""
        ),
    ]
    return nbf.v4.new_notebook(
        cells=cells,
        metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
    )


def build_torch() -> nbf.NotebookNode:
    cells = [
        md(
            """
# Lakeside PyTorch — results viewer

**Training does not run in this notebook.** Use the parallel CLI:

```powershell
cd vibe_code_apps_22
$env:VIBE22_ALLOW_CLI_TRAIN="1"
python scripts/train_four_arms.py --profile full_evaluation
# torch-only: python scripts/train_four_arms.py --arms torch_winter torch_allyear
```

This notebook compares `torch_winter` vs `torch_allyear` timings and metrics.
"""
        ),
        code(SETUP),
        md("## Load run index + cards"),
        code_raw(LOAD_RUNS),
        md("## Train times"),
        code_raw(TIMING_BARS),
        code_raw(DETAIL),
        md("## Torch metrics (winter vs all-year)"),
        code_raw("FAMILY = 'torch'\nfrom IPython.display import HTML\n" + METRICS),
        md(
            """
## Notes

- Lean torch default in `train_arm.py`: 1 seed / ResMLP. Pass `--full-torch` on the launcher for 5 seeds + GRU.
- Torch never overwrites the sklearn desktop hybrid champion.
"""
        ),
    ]
    return nbf.v4.new_notebook(
        cells=cells,
        metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
    )


def main() -> int:
    NB_DIR.mkdir(parents=True, exist_ok=True)
    sk = NB_DIR / "lakeside_heating_dsm_sklearn.ipynb"
    tor = NB_DIR / "lakeside_heating_dsm_torch.ipynb"
    nbf.write(build_sklearn(), sk)
    nbf.write(build_torch(), tor)
    print("wrote", sk)
    print("wrote", tor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
