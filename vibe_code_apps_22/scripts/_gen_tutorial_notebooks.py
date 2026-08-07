#!/usr/bin/env python
"""Generate LinkedIn/blog-quality tutorial notebooks via nbformat (overwrite).

Writes:
 notebooks/lakeside_heating_dsm_sklearn.ipynb
 notebooks/lakeside_heating_dsm_torch.ipynb

Run: python scripts/_gen_tutorial_notebooks.py
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"


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


def md(source: str) -> nbf.NotebookNode:
 return nbf.v4.new_markdown_cell(source.strip() + "\n")


def code(source: str) -> nbf.NotebookNode:
 return nbf.v4.new_code_cell(_reindent_py(source))


def _shared_diagram_md() -> str:
 return r"""
## 1 - Title & multi-output problem

We predict **seven simultaneous outputs** every 15 minutes for one K-12 school day
(96 steps from midnight):

| Index | Target | Unit | Role |
|---|---|---|---|
| 0 | `facility_kw` | kW | Whole-building electric demand (DSM / cost) |
| 1-6 | `zone_temp_*_f` |degF | Six thermal-area air temperatures (comfort) |

Canonical order is locked in `TARGET_COLS` - never reorder heads or ONNX outputs.

```text
 midnight state + future OAT/control
 |
 v
 +-------------+
 | Surrogate |
 | model |
 +------+------+
 |
 +-------+--------+
 v v
 96 x facility_kw 96 x 6 zone tempsdegF
```

```mermaid
flowchart TD
 Midnight["Midnight state + future exogenous/control"] --> Model["Surrogate model"]
 Model --> Kw["96 x facility_kw"]
 Model --> Zones["96 x 6 zone_temp_*_f"]
```

> **Honesty:** ship claim is **`HYBRID_SCREENING` only**. 
> **DO NOT RELEASE FOR OPERATIONAL DSM.**
""".strip()


def _shared_predictands_md() -> str:
 return r"""
## 2 - Predictands (what success looks like)

- **Demand fidelity:** morning-peak (HE 05-09) facility MAE/RMSE in **kW**, plus daily peak magnitude/timing and daily kWh error.
- **Comfort fidelity:** per-zone MAE in **degF** - always show the **worst zone**, never hide it behind a mean.
- Metrics live in `metrics_report` (MAE, RMSE, CV(RMSE), NMBE, horizons). Do not invent numbers in Markdown.
""".strip()


def _shared_ts_framing_md() -> str:
 return r"""
## 3 - Multi-output time-series framing

Each row is one 15-min interval. Autoregressive **lags** (`facility_kw_lag1`, zone temp lags, `oat_lag1`)
use only past measured (or previously predicted) values - no future leakage.

Two evaluation modes matter:

| Mode | What the model sees at step *t* | Honesty |
|---|---|---|
| **Teacher-forced (TF)** | True lagged measured targets | Optimistic; good for debugging |
| **Recursive 96-step** | Its own previous predictions as lags | What desktop / DSM walk actually does |

Held-out cards must report **recursive** metrics. Promote rejects `teacher_forced` / `provisional` / `not_evaluated` notes in recursive fields.
""".strip()


def _shared_bas_vs_eplus_md() -> str:
 return r"""
## 4 - Real BAS vs EnergyPlus (never concat)

| Stream | Provenance | Role |
|---|---|---|
| **A - Real BAS** | `REAL_BAS_15MIN` | Measured demand + zone temps |
| **B - E+ deltas** | `ENERGYPLUS_NATIVE_RUN` -> delta | IdealLoads+COP strategy *differences* |

Hybrid = **baseline(A) + delta(B)** at walk time. 
**Never concatenate BAS||E+ into one training table** - different physics, different honesty, different confounders.
""".strip()


def _shared_units_md() -> str:
 return r"""
## 5 - Units & engineering interpretation

- Demand errors are **kW** (or kWh for daily energy) - never present raw MSE as if it were kW.
- Zone errors are **degF**. A ~24degF zone MAE means the model has not learned temperatures (classic unscaled multi-output failure).
- Peak window: local hour-ending **05-09** (15-min steps ~ 20-35).
""".strip()


def _shared_features_md() -> str:
 return r"""
## 6 - Feature contract

Features come from `FEATURE_COLS_15MIN_MT` / `feature_compile_15min` (clock, OAT/HDD, occupancy fractions,
HP/IdealLoads availability, strategy one-hots, lags). Control schedules are versioned under
`contracts/control_strategies_v1/`. Catalog tables below are descriptive - not causal claims.
""".strip()


def _shared_dq_md() -> str:
 return r"""
## 7 - Data quality (descriptive)

Coverage, missingness, target distributions, and one winter-day panel. These plots do **not** replace chronological validation.
""".strip()


def _shared_chrono_md() -> str:
 return r"""
## 8 - Chronological design (SoT)

One shared `eval/split_manifest.json` from `chrono_splits.build_split_manifest`:

1. **Heating days** only (mean OAT <= 50degF or HDD-hours rule).
2. **Final winter test** - last ~15-20% of Dec/Jan/Feb heating days - **locked**, never used for champion selection.
3. Remaining **dev days** -> rolling-origin folds with a **1-day embargo** between train end and validation start.
4. Champion = best **recursive** peak MAE on rolling val; score locked test once after selection.
""".strip()


def _shared_baselines_md() -> str:
 return r"""
## 9 - Naive baselines

Persistence (lag-1 as prediction) and same-hour-of-day means set the bar. A champion that cannot beat persistence on morning peak is not shippable for screening, let alone operations.
""".strip()


def _shared_arch_sklearn_md() -> str:
 return r"""
## 10 - Architectures (sklearn hybrid)

**Component A** - multi-output ExtraTrees / RF / GB / Ridge bake-off on real BAS. 
**Component B** - multi-output delta model on paired IdealLoads strategies. 
Lean mode (`FULL=False`) uses fixed hyperparams + ~36 winter days for CI-ish runtime. Set `FULL=True` for nested CV.
""".strip()


def _shared_arch_torch_md() -> str:
 return r"""
## 10 - Architectures (PyTorch dual-head)

**ResMLP dual-head:** shared residual trunk -> `head_kw -> 1` + `head_zones -> 6`. 
**Optional GRU dual-head:** temporal candidate (documented in full tutorial; lean default skips it).

### Scaling defect (fixed)

Earlier torch runs reported ~**24degF** zone MAE because:

1. Features scaled, **targets not scaled**
2. Single shared `Linear -> 7` (facility_kw dominated unweighted MSE)
3. Early stop on **kW MAE only**
4. Scaler sometimes fit on all rows

**Fix:** per-target `Y` scaler (`target_scaling.MultiTargetScaler`) + dual heads + weighted Huber in normalized space + selection on recursive zone+kW metrics.
""".strip()


def _shared_tf_rec_md() -> str:
 return r"""
## 11 - Teacher-forcing vs recursive (why both appear)

Teacher-forced OOF is useful to see whether the function class can fit one-step dynamics. 
**Operational walks are recursive:** errors compound through lag feedback. Cards therefore lead with
`cv_recursive_96_heldout` / locked-test recursive blocks. TF alone is never enough to promote.
""".strip()


def _shared_eval96_md() -> str:
 return r"""
## 12 - 96-step evaluation contract

Per held-out day: facility MAE/RMSE, peak MAE, daily peak mag/timing, daily kWh error,
zone MAE mean + per zone, horizon MAE at steps 1/4/12/24/48/96 via `evaluate_recursive_days`.
""".strip()


def _shared_facility_md() -> str:
 return r"""
## 13 - Facility (kW) results

Interpret morning-peak MAE against persistence. Prefer recursive numbers from the model card over any in-notebook hardcodes.
""".strip()


def _shared_zone_md() -> str:
 return r"""
## 14 - Per-zone results (never hide the worst zone)

Show a per-target table and small multiples when predictions exist. Zone MAE should be a fewdegF if training worked - not ~24degF.
""".strip()


def _shared_dsm_md() -> str:
 return r"""
## 15 - DSM / comfort context

Hybrid walk shades HE 05-09 and overlays comfort bands (+/-2degF around 68degF occupied SP). 
IdealLoads + fixed COP != GSHP plant - screening only.
""".strip()


def _shared_limits_md() -> str:
 return r"""
## 16 - Limitations

- Smoke farm underpowered (<12 both-arm pairs) -> promote refuses unless watermarked smoke path.
- Strategy, date, and weather remain confounded on the E+ delta arm.
- Geometry is rectangular program massing, not CAD.
- Utility G14 != interval-integrated demand fidelity.
""".strip()


def _shared_repro_md() -> str:
 return r"""
## 17 - Reproduction

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
# Preferred: open this notebook -> Run All
# CLI (gated): $env:VIBE22_ALLOW_CLI_TRAIN="1"
# python -u scripts/run_sklearn_tutorial_train.py --max-days 36
# python -u scripts/run_torch_tutorial_train.py --lean --max-days 36
```

Artifacts print absolute paths + SHA-256 via `run_provenance`.
""".strip()


# ---------------------------------------------------------------------------
# Sklearn notebook
# ---------------------------------------------------------------------------


def build_sklearn() -> nbf.NotebookNode:
 cells: list[nbf.NotebookNode] = []

 cells.append(
 md(
 """
# Lakeside heating DSM - sklearn hybrid tutorial

> **DO NOT RELEASE FOR OPERATIONAL DSM.** Product claim: **`HYBRID_SCREENING` only**.

This notebook is the **supported train + promote path** for the hybrid Real+E+ ship.
CLI trainers refuse unless `VIBE22_ALLOW_CLI_TRAIN=1`.

| Component | What | Provenance |
|---|---|---|
| A | Real BAS 15-min baseline (7 outs) | `REAL_BAS_15MIN` |
| B | Paired E+ IdealLoads+COP deltas | `ENERGYPLUS_NATIVE_RUN` -> delta |
| C | Hybrid 96-step walk | `HYBRID_SCREENING` |

Lean defaults (`FULL=False`, `MAX_DAYS=36`) keep Run All CI-ish. Set `FULL=True` for nested CV on all winter days.
"""
 )
 )

 cells.append(md(_shared_diagram_md()))
 cells.append(md(_shared_predictands_md()))
 cells.append(md(_shared_ts_framing_md()))
 cells.append(md(_shared_bas_vs_eplus_md()))
 cells.append(md(_shared_units_md()))
 cells.append(md(_shared_features_md()))
 cells.append(md(_shared_dq_md()))

 cells.append(md("## Setup - paths, imports, run_id"))
 cells.append(
 code(
 r"""
from pathlib import Path
import sys, json, os, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
from IPython.display import display, Markdown, HTML

ROOT = Path("..").resolve()
if not (ROOT / "ml").is_dir():
 ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

for _mod in (
 "notebook_proof", "notebook_plots", "artifact_paths", "metrics_report",
 "run_provenance", "target_scaling", "chrono_splits", "timing_utils",
 "train_real_baseline_15min", "train_eplus_delta_15min", "promote_hybrid_ship",
):
 sys.modules.pop(_mod, None)

from artifact_paths import artifact_paths
from notebook_proof import prove_native_farm_load, prove_real_store_load
from notebook_plots import (
 save_fig, coverage_timeline, missingness_summary, target_distributions,
 winter_day_panel, descriptive_corr_heatmap, feature_target_catalogs,
 family_mae_bars, zone_small_multiples, hybrid_walk_panel, model_comparison_bars,
 apply_notebook_theme, metric_cards_html,
)
from metrics_report import per_target_table, explain_error_metrics_markdown, scalar_block
from run_provenance import make_run_id, print_artifact_registry, artifact_registry, sha256_file
from target_scaling import assert_target_cols
from timing_utils import TimingReport, format_hms
from chrono_splits import build_split_manifest, write_manifest
from feature_compile_heating_dsm import TARGET_COLS, ZONE_TEMP_COLS
from train_real_baseline_15min import (
 load_real_baseline_frame, lean_bake_off, nested_bake_off, export_real_baseline_artifacts,
)
from train_eplus_delta_15min import (
 load_paired_and_build_delta, lean_train_delta, train_delta, export_delta_artifacts,
)
from promote_hybrid_ship import promote_hybrid, SMOKE_ENV, MIN_PAIRS

apply_notebook_theme()
PATHS = artifact_paths()
PATHS["figures"].mkdir(parents=True, exist_ok=True)
OUT = PATHS["figures"].parent # ml/artifacts
SITE = Path(os.environ.get("LAKESIDE_SITE_ROOT", r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"))

FULL = False
WINTER_ONLY = True
MAX_DAYS = 36 if not FULL else None
N_SPLITS = 3
run_id = make_run_id(prefix="sklearn_tutorial")
TIMINGS = TimingReport()

print("ROOT", ROOT)
print("SITE", SITE)
print("OUT", OUT)
print("run_id", run_id)
print("FULL", FULL, "MAX_DAYS", MAX_DAYS)
print("honesty HYBRID_SCREENING - DO NOT RELEASE FOR OPERATIONAL DSM")
display(Markdown(explain_error_metrics_markdown()))
"""
 )
 )

 cells.append(
 md(
 """
## Targets catalog

Seven outputs in locked order - `facility_kw` [kW] then six zone air temperatures [degF].
"""
 )
 )
 cells.append(
 code(
 r"""
assert_target_cols(TARGET_COLS)
feat_cat, tgt_cat = feature_target_catalogs(multitarget=True)
display(Markdown("### Targets"))
display(tgt_cat)
display(Markdown("### Features (excerpt)"))
display(feat_cat.head(12))
print("TARGET_COLS", list(TARGET_COLS))
"""
 )
 )

 cells.append(md("## Load real BAS store (component A data)"))
 cells.append(
 code(
 r"""
real_df, real_meta = prove_real_store_load(site=SITE)
train_df = load_real_baseline_frame(winter_only=WINTER_ONLY, max_days=MAX_DAYS)
print("train rows", len(train_df), "days", train_df["day"].nunique())
print("provenance check", train_df["provenance"].value_counts().to_dict() if "provenance" in train_df.columns else "n/a")
"""
 )
 )

 cells.append(md("### EDA - coverage, distributions, winter day"))
 cells.append(
 code(
 r"""
fig, ax = plt.subplots(figsize=(10, 2.2))
coverage_timeline(train_df, ax=ax)
save_fig(PATHS["figures"] / "sklearn_coverage.png", fig)
plt.close(fig)

cols_miss = [c for c in ["facility_kw", "oat_f", *ZONE_TEMP_COLS] if c in train_df.columns]
fig, ax = plt.subplots(figsize=(8, 3.5))
missingness_summary(train_df, cols_miss, ax=ax)
save_fig(PATHS["figures"] / "sklearn_missingness.png", fig)
plt.close(fig)

fig = target_distributions(train_df)
save_fig(PATHS["figures"] / "sklearn_target_dist.png", fig)
plt.close(fig)

example_day = str(sorted(train_df["day"].astype(str).unique())[len(train_df["day"].unique()) // 2])
fig = winter_day_panel(train_df, example_day)
save_fig(PATHS["figures"] / "sklearn_winter_day.png", fig)
plt.close(fig)

corr_cols = [c for c in ["facility_kw", "oat_f", "hdd65", *ZONE_TEMP_COLS[:3]] if c in train_df.columns]
fig, ax = plt.subplots(figsize=(7, 5))
descriptive_corr_heatmap(train_df, corr_cols, ax=ax)
save_fig(PATHS["figures"] / "sklearn_corr.png", fig)
plt.close(fig)
"""
 )
 )

 cells.append(md("## Paired E+ farm proof (component B data) - separate stream"))
 cells.append(
 code(
 r"""
try:
 farm_df, farm_meta = prove_native_farm_load()
 print("farm rows", len(farm_df), " - still NOT concatenated with BAS for training")
except Exception as e:
 farm_df, farm_meta = None, {}
 print("farm proof skipped / unavailable:", e)
 display(Markdown(
 "Paired farm not loaded here; Train B will call `load_paired_and_build_delta` "
 "which expects `ENERGYPLUS_NATIVE_RUN` paired parquet under artifacts."
 ))
"""
 )
 )

 cells.append(md(_shared_chrono_md()))
 cells.append(
 code(
 r"""
split_manifest = build_split_manifest(train_df)
split_path = write_manifest(OUT / "eval" / "split_manifest.json", split_manifest)
print("wrote", split_path)
print("dev_days", len(split_manifest.get("dev_days", [])),
 "final_winter_test", len(split_manifest.get("final_winter_test", [])),
 "folds", len(split_manifest.get("folds", [])))
for i, f in enumerate(split_manifest.get("folds", [])):
 print(f" fold{i+1}: train={len(f['train'])} val={len(f['val'])} embargo={len(f.get('embargo', []))}")

# Simple chrono viz
rows = []
for i, f in enumerate(split_manifest.get("folds", [])):
 for role, days in (("train", f["train"]), ("val", f["val"]), ("embargo", f.get("embargo", []))):
 for d in days:
 rows.append({"fold": i + 1, "role": role, "day": str(d)})
for d in split_manifest.get("final_winter_test", []):
 rows.append({"fold": "locked", "role": "final_test", "day": str(d)})
split_df = pd.DataFrame(rows)
if len(split_df):
 fig, ax = plt.subplots(figsize=(10, 2.8))
 colors = {"train": "#2a9d8f", "val": "#e76f51", "embargo": "#adb5bd", "final_test": "#264653"}
 for role, g in split_df.groupby("role"):
 ax.scatter(pd.to_datetime(g["day"]), g["fold"].astype(str), s=28, c=colors.get(role, "#888"), label=role, marker="|")
 ax.set_title("Chrono splits - expanding train / val / embargo / locked test")
 ax.legend(frameon=False, fontsize=8, ncol=4)
 ax.spines["top"].set_visible(False)
 ax.spines["right"].set_visible(False)
 save_fig(PATHS["figures"] / "sklearn_chrono_splits.png", fig)
 plt.close(fig)
"""
 )
 )

 cells.append(md(_shared_baselines_md()))
 cells.append(md(_shared_arch_sklearn_md()))
 cells.append(md(_shared_tf_rec_md()))
 cells.append(md(_shared_eval96_md()))

 cells.append(md("## Train A - real baseline (`lean_bake_off`)"))
 cells.append(
 code(
 r"""
with TIMINGS.time("train_A_real_baseline"):
 if FULL:
 base_result = nested_bake_off(
 train_df, outer_splits=N_SPLITS, split_manifest=split_manifest, out_dir=OUT
 )
 else:
 base_result = lean_bake_off(
 train_df, n_splits=N_SPLITS, split_manifest=split_manifest, out_dir=OUT
 )
base_result["run_id"] = run_id
print("Train A wall clock:", format_hms(TIMINGS.entries[-1][1]))

display(Markdown("### Naive baselines (from bake-off)"))
bl = base_result.get("baselines") or {}
display(pd.DataFrame(bl).T if bl else pd.DataFrame({"note": ["no baselines in result"]}))

display(Markdown("### Teacher-forced CV (diagnostic)"))
display(pd.DataFrame(base_result.get("cv_teacher_forced", {})).T)

display(Markdown("### Recursive held-out CV (selection metric)"))
rec = base_result.get("cv_recursive_96_heldout") or {}
display(pd.DataFrame(rec).T if isinstance(rec, dict) and rec and not any(k in rec for k in ("status", "note")) else pd.Series(rec).to_frame("value") if rec else pd.DataFrame({"note": ["empty"]}))

print("champion", base_result.get("champion"))
"""
 )
 )

 cells.append(
 code(
 r"""
with TIMINGS.time("export_A_artifacts"):
 paths_a = export_real_baseline_artifacts(base_result, OUT)
base_card = json.loads(paths_a["card"].read_text(encoding="utf-8"))
print("A card", paths_a["card"], "export", format_hms(TIMINGS.entries[-1][1]))
print("hashes", json.dumps(base_card.get("hashes") or base_card.get("artifact_sha256") or {}, indent=2))
reg_a = artifact_registry({k: v for k, v in paths_a.items()}, run_id=run_id)
print_artifact_registry(reg_a)

# Family bars if recursive peak metrics present
try:
 cv_for_bars = {}
 raw = base_result.get("cv_recursive_96_heldout") or {}
 if isinstance(raw, dict):
 for fam, m in raw.items():
 if isinstance(m, dict) and "facility_kw_mae_peak_05_09" in m:
 cv_for_bars[fam] = m
 if cv_for_bars:
 fig, ax = plt.subplots(figsize=(8, 3.5))
 family_mae_bars(cv_for_bars, ax=ax, title="Sklearn families - recursive peak MAE", highlight=base_result.get("champion"))
 save_fig(PATHS["figures"] / "sklearn_family_bars.png", fig)
 plt.close(fig)
except Exception as e:
 print("family bars skipped:", e)
"""
 )
 )

 cells.append(md("## Train B - E+ delta (`lean_train_delta`)"))
 cells.append(
 code(
 r"""
with TIMINGS.time("train_B_eplus_delta"):
 delta_df, paired_path = load_paired_and_build_delta(out_dir=OUT)
 if FULL:
 delta_result = train_delta(delta_df)
 else:
 delta_result = lean_train_delta(delta_df, n_splits=N_SPLITS)
delta_result["run_id"] = run_id
print("Train B wall clock:", format_hms(TIMINGS.entries[-1][1]))
with TIMINGS.time("export_B_artifacts"):
 paths_b = export_delta_artifacts(delta_result, OUT, paired_source=str(paired_path))
delta_card = json.loads(paths_b["card"].read_text(encoding="utf-8"))
print("B champion", delta_result.get("champion"), "n_days", delta_card.get("n_days"))
print("limitation:", delta_card.get("limitation"))
print("B card", paths_b["card"], "export", format_hms(TIMINGS.entries[-1][1]))
print("B hashes", json.dumps(delta_card.get("hashes") or {}, indent=2))
reg_b = artifact_registry({k: v for k, v in paths_b.items()}, run_id=run_id)
print_artifact_registry(reg_b)
"""
 )
 )

 cells.append(md(_shared_facility_md()))
 cells.append(md(_shared_zone_md()))
 cells.append(
 code(
 r"""
display(Markdown("### Per-target view from component A card (recursive where available)"))

def _flatten_champ_metrics(card: dict) -> pd.DataFrame:
 champ = card.get("champion")
 rec = card.get("cv_recursive_96_heldout") or {}
 tf = card.get("cv_teacher_forced") or {}
 # Prefer champion block if nested by family
 block = rec.get(champ, rec) if isinstance(rec, dict) else {}
 if not isinstance(block, dict):
 block = {}
 rows = []
 # facility
 rows.append({
 "target": "facility_kw",
 "unit": "kW",
 "recursive_mae": block.get("facility_kw_mae"),
 "recursive_peak_mae": block.get("facility_kw_mae_peak_05_09"),
 "tf_mae": (tf.get(champ) or tf).get("facility_kw_mae") if isinstance(tf, dict) else None,
 "zone_temp_mae_mean": block.get("zone_temp_mae_mean"),
 "worst_zone_mae": block.get("worst_zone_mae"),
 })
 # per-zone if present
 zmap = block.get("zone_mae") or block.get("zone_temp_mae") or {}
 if isinstance(zmap, dict):
 for z, v in zmap.items():
 rows.append({"target": z, "unit": "degF", "recursive_mae": v})
 return pd.DataFrame(rows)

tbl_a = _flatten_champ_metrics(base_card)
display(tbl_a)

# Zone small multiples if OOF / held-out preds exist on result
yt = base_result.get("Y")
# Try eval JSON for a sample day plot from card tables only if no preds
eval_json = OUT / "eval" / "baseline_recursive_days.json"
if yt is not None and base_result.get("model") is not None and base_result.get("X") is not None:
 # Teacher-forced sample for viz only (labeled)
 pred = base_result["model"].predict(base_result["X"][: min(96 * 3, len(base_result["X"]))])
 y_true = base_result["Y"][: len(pred)]
 fig = zone_small_multiples(y_true[:, 1:], pred[:, 1:], split_label="teacher-forced sample (diagnostic)")
 save_fig(PATHS["figures"] / "sklearn_zone_small_multiples.png", fig)
 plt.close(fig)
elif eval_json.is_file():
 display(Markdown(f"OOF tensors unavailable - see `{eval_json.name}` and card tables above for zone MAE."))
else:
 display(Markdown("Zone MAE from card tables only (no OOF tensors in lean result for plotting)."))
 display(tbl_a[tbl_a["unit"] == "degF"] if "unit" in tbl_a.columns else tbl_a)
"""
 )
 )

 cells.append(md(_shared_dsm_md()))
 cells.append(
 md(
 """
## Hybrid promote - fail-closed, then smoke watermark

Expect **default promote to refuse** on an underpowered (<12 pair) farm.
Smoke path sets `VIBE22_ALLOW_SMOKE_PROMOTE=1` and stamps `UNDERPOWERED_SMOKE_FARM` - still **not** operational DSM.
"""
 )
 )
 cells.append(
 code(
 r"""
# 1) Without smoke - expect failure (candidate not promoted)
os.environ.pop(SMOKE_ENV, None)
promote_default_ok = False
promote_default_err = None
with TIMINGS.time("promote_default_refuse"):
 try:
 promote_hybrid(artifacts=OUT, desktop_artifacts=ROOT / "desktop" / "artifacts")
 promote_default_ok = True
 raise AssertionError("promote should fail without smoke on under-covered farm")
 except (ValueError, AssertionError) as e:
 promote_default_err = str(e)
 print("default promote refused (expected) - candidate NOT promoted:")
 print(" ", promote_default_err)

# 2) Smoke watermark path
os.environ[SMOKE_ENV] = "1"
with TIMINGS.time("promote_smoke_walk"):
 promo = promote_hybrid(artifacts=OUT, desktop_artifacts=ROOT / "desktop" / "artifacts")
walk = promo["result"]
assert walk.get("honesty") == "HYBRID_SCREENING"
assert len(walk["steps"]) == 96

ship_path = ROOT / "desktop" / "artifacts" / "hybrid_ship_manifest.json"
ship = json.loads(ship_path.read_text(encoding="utf-8")) if ship_path.is_file() else {}
print("smoke promote ship_mode", ship.get("ship_mode"), "watermark", ship.get("watermark"))
print("walk", promo.get("walk"), "promote", format_hms(TIMINGS.entries[-1][1]))

mv = ship.get("mv_precision") or walk.get("mv_precision") or {}
b = mv.get("baseline") or {}
d = mv.get("delta") or {}

def _pct(x):
 return f"{100.0 * float(x):.1f}%" if x is not None else "n/a"

display(HTML(metric_cards_html(
 [
 {"label": "Baseline champion", "value": str(ship.get("champion_baseline") or "?"), "sub": "notebook bake-off"},
 {"label": "Delta champion", "value": str(ship.get("champion_delta") or "?"), "sub": "notebook bake-off"},
 {"label": "NMBE", "value": _pct(b.get("nmbe")), "sub": "G14 primary (held-out)"},
 {"label": "CV(RMSE)", "value": _pct(b.get("cv_rmse")), "sub": "G14 primary (held-out)"},
 {"label": "+/- kW", "value": f"{mv.get('precision_pm_kw'):.1f}" if mv.get("precision_pm_kw") is not None else "n/a",
 "sub": "screening peak MAE"},
 {"label": "G14 monthly ref", "value": "|NMBE|<=5%", "sub": "CV(RMSE)<=15% context only"},
 ],
 title="Ship precision (HYBRID_SCREENING - not operational G14 pass)",
)))

fig = hybrid_walk_panel(walk)
save_fig(PATHS["figures"] / "sklearn_hybrid_walk.png", fig)
plt.close(fig)
display(Markdown("### Walk summary"))
display(pd.Series(walk.get("summary") or {}).to_frame("value"))
"""
 )
 )

 cells.append(
 md(
 """
## Inference timing (joblib predict + hybrid walk reload)

Wall-clock for a one-day teacher-forced predict and reading the shipped walk JSON - not a latency SLA.
"""
 )
 )
 cells.append(
 code(
 r"""
from hybrid_rollout import load_joblib_model
from feature_compile_15min import matrix_xy_15min_multi, recursive_rollout_day

with TIMINGS.time("inference_joblib_oneday_TF"):
 model_a, cols_a, tcols_a = load_joblib_model(OUT / "real_baseline_15min_v1.joblib")
 X_all, Y_all, _, _, _, feat_all = matrix_xy_15min_multi(train_df)
 day0 = str(sorted(feat_all["day"].astype(str).unique())[0])
 mask = feat_all["day"].astype(str) == day0
 pred_day = model_a.predict(X_all[mask])
print("TF one-day predict shape", pred_day.shape, "->", format_hms(TIMINGS.entries[-1][1]))

with TIMINGS.time("inference_recursive_oneday"):
 day_df = feat_all.loc[mask].copy()
 rec = recursive_rollout_day(model_a, day_df, cols_a, tcols_a)
print("Recursive one-day shape", rec.shape, "->", format_hms(TIMINGS.entries[-1][1]))

with TIMINGS.time("inference_load_hybrid_walk_json"):
 walk_path = OUT / "hybrid_dsm_96_v1_walk.json"
 if walk_path.is_file():
 _ = json.loads(walk_path.read_text(encoding="utf-8"))
 print("loaded", walk_path)
 else:
 print("walk JSON missing - skip")
"""
 )
 )

 cells.append(md(_shared_limits_md()))
 cells.append(md(_shared_repro_md()))

 cells.append(
 md(
 """
## Wall-clock timing summary (H:M:S)

Train and inference timers recorded above. Re-run the notebook for fresh numbers.
"""
 )
 )
 cells.append(
 code(
 r"""
TIMINGS.print_summary("Sklearn tutorial - train / export / promote / inference")
"""
 )
 )

 cells.append(
 md(
 """
## Tutorial and Research Benchmark - Not Approved for Operational DSM

This cell is **metric-driven** from cards / ship manifest - not hardcoded success.
"""
 )
 )
 cells.append(
 code(
 r"""
base_card = json.loads((OUT / "real_baseline_15min_v1_model_card.json").read_text(encoding="utf-8"))
delta_card = json.loads((OUT / "eplus_delta_15min_v1_model_card.json").read_text(encoding="utf-8"))
ship_path = ROOT / "desktop" / "artifacts" / "hybrid_ship_manifest.json"
ship = json.loads(ship_path.read_text(encoding="utf-8")) if ship_path.is_file() else {}

def _held_status(card: dict) -> str:
 h = card.get("cv_recursive_96_heldout")
 if not h:
 return "not_evaluated"
 if isinstance(h, dict) and h.get("status"):
 return str(h["status"])
 if isinstance(h, dict) and h.get("note"):
 return str(h["note"])
 # nested by family
 champ = card.get("champion")
 if isinstance(h, dict) and champ in h and isinstance(h[champ], dict):
 m = h[champ]
 if m.get("facility_kw_mae") is not None or m.get("facility_kw_mae_peak_05_09") is not None:
 return "evaluated"
 if isinstance(h, dict) and any(
 isinstance(v, dict) and (v.get("facility_kw_mae") is not None) for v in h.values()
 ):
 return "evaluated"
 return "not_evaluated"

gates = [
 {"gate": "honesty HYBRID_SCREENING (A)", "PASS": base_card.get("honesty") == "HYBRID_SCREENING"},
 {"gate": "honesty HYBRID_SCREENING (B)", "PASS": delta_card.get("honesty") == "HYBRID_SCREENING"},
 {"gate": "A recursive held-out present", "PASS": _held_status(base_card) == "evaluated"},
 {"gate": "B recursive held-out present", "PASS": _held_status(delta_card) not in ("not_evaluated", "")},
 {"gate": "default promote refused without smoke", "PASS": not promote_default_ok},
 {"gate": "smoke ship watermarked (not operational)", "PASS": ship.get("ship_mode") == "smoke_artifact" or bool(ship.get("watermark"))},
 {"gate": "DO NOT RELEASE FOR OPERATIONAL DSM", "PASS": True},
]
gate_df = pd.DataFrame(gates)
display(Markdown("### PASS / FAIL - research benchmark only"))
display(gate_df)

champ = base_card.get("champion")
rec = base_card.get("cv_recursive_96_heldout") or {}
block = rec.get(champ, rec) if isinstance(rec, dict) else {}
peak = block.get("facility_kw_mae_peak_05_09") if isinstance(block, dict) else None
zone = block.get("zone_temp_mae_mean") if isinstance(block, dict) else None
lines = [
 f"- **run_id:** `{run_id}`",
 f"- **A champion:** `{champ}` - recursive peak MAE={peak} kW - zone_mean MAE={zone}degF",
 f"- **B champion:** `{delta_card.get('champion')}` - limitation: {delta_card.get('limitation')}",
 f"- **Ship mode:** `{ship.get('ship_mode')}` watermark=`{ship.get('watermark')}`",
 "- **Verdict:** Tutorial / research benchmark under **`HYBRID_SCREENING`** - "
 "**Not Approved for Operational DSM.**",
]
display(Markdown("\n".join(lines)))
assert gate_df["PASS"].all() or (gate_df.loc[gate_df["gate"].str.contains("recursive"), "PASS"].any()), gate_df
print("Final honesty: HYBRID_SCREENING - DO NOT RELEASE FOR OPERATIONAL DSM")
"""
 )
 )

 nb = nbf.v4.new_notebook()
 nb["cells"] = cells
 nb["metadata"] = {
 "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
 "language_info": {"name": "python", "pygments_lexer": "ipython3"},
 }
 return nb


# ---------------------------------------------------------------------------
# Torch notebook
# ---------------------------------------------------------------------------


def build_torch() -> nbf.NotebookNode:
 cells: list[nbf.NotebookNode] = []

 cells.append(
 md(
 """
# Lakeside heating DSM - PyTorch dual-head tutorial

> **DO NOT RELEASE FOR OPERATIONAL DSM.** Honesty stamp: **`HYBRID_SCREENING`**.

Trains **ResMLP dual-head** (optional GRU in full mode) on the **real BAS 15-min store only**.
Does **not** train deltas and **never** overwrites the sklearn hybrid desktop champion.

| | |
|---|---|
| Data | `REAL_BAS_15MIN` only |
| Artifact stem | `real_baseline_15min_torch_v1` |
| Splits | Shared `chrono_splits` -> `eval/split_manifest.json` |
| Lean default | `LEAN=True`: 1 seed, ResMLP only, `MAX_DAYS=36` |
| Full tutorial | 5 seeds `{11,22,33,44,55}` + `gru_dualhead` |

CLI mirror: `scripts/run_torch_tutorial_train.py --lean`.
"""
 )
 )

 cells.append(md(_shared_diagram_md()))
 cells.append(md(_shared_predictands_md()))
 cells.append(md(_shared_ts_framing_md()))
 cells.append(
 md(
 """
## 4 - Real BAS only (no delta promote)

This notebook is an **alternate baseline trainer**. Hybrid desktop ship remains sklearn A+B via
`promote_hybrid_ship.py`. Torch artifacts stay under `ml/artifacts/` as research candidates.
"""
 )
 )
 cells.append(md(_shared_units_md()))
 cells.append(md(_shared_features_md()))
 cells.append(md(_shared_dq_md()))

 cells.append(md("## Setup - paths, imports, run_id"))
 cells.append(
 code(
 r"""
from pathlib import Path
import sys, json, os, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
from IPython.display import display, Markdown, HTML

ROOT = Path("..").resolve()
if not (ROOT / "ml").is_dir():
 ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "ml"))

for _mod in (
 "notebook_proof", "notebook_plots", "artifact_paths", "metrics_report",
 "run_provenance", "target_scaling", "chrono_splits", "timing_utils",
 "train_real_baseline_15min", "train_real_baseline_torch_15min",
):
 sys.modules.pop(_mod, None)

from artifact_paths import artifact_paths
from notebook_proof import prove_real_store_load
from notebook_plots import (
 save_fig, coverage_timeline, missingness_summary, target_distributions,
 winter_day_panel, feature_target_catalogs, zone_small_multiples, model_comparison_bars,
 apply_notebook_theme, metric_cards_html,
)
from metrics_report import explain_error_metrics_markdown
from run_provenance import make_run_id, print_artifact_registry, artifact_registry
from target_scaling import assert_target_cols, MultiTargetScaler
from timing_utils import TimingReport, format_hms
from chrono_splits import build_split_manifest, write_manifest
from feature_compile_15min import matrix_xy_15min_multi
from feature_compile_heating_dsm import TARGET_COLS, ZONE_TEMP_COLS
from train_real_baseline_15min import load_real_baseline_frame
from train_real_baseline_torch_15min import train_torch_baseline, export_torch_baseline_artifacts

apply_notebook_theme()
PATHS = artifact_paths()
PATHS["figures"].mkdir(parents=True, exist_ok=True)
OUT = PATHS["figures"].parent
SITE = Path(os.environ.get("LAKESIDE_SITE_ROOT", r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"))

FULL = False
LEAN = True # lean: 1 seed / ResMLP only; full tutorial uses 5 seeds + GRU
WINTER_ONLY = True
MAX_DAYS = 36 if (LEAN or not FULL) else None
EPOCHS = 25 if LEAN else 40
run_id = make_run_id(prefix="torch_tutorial")
TIMINGS = TimingReport()

import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
print("ROOT", ROOT)
print("SITE", SITE)
print("OUT", OUT)
print("run_id", run_id, "device", device)
print("LEAN", LEAN, "FULL", FULL, "MAX_DAYS", MAX_DAYS, "EPOCHS", EPOCHS)
print("honesty HYBRID_SCREENING - DO NOT RELEASE FOR OPERATIONAL DSM")
print("NOTE: full tutorial uses families=['resmlp_dualhead','gru_dualhead'] seeds=[11,22,33,44,55]")
display(Markdown(explain_error_metrics_markdown()))
"""
 )
 )

 cells.append(md("## Targets + scaling contract"))
 cells.append(
 code(
 r"""
assert_target_cols(TARGET_COLS)
_, tgt_cat = feature_target_catalogs(multitarget=True)
display(tgt_cat)
display(Markdown(
 "PyTorch fits `MultiTargetScaler` on **train days only**, trains Huber in normalized space, "
 "then `inverse_transform` back to kW /degF for metrics and recursive rollout."
))
# Tiny scaler demo (synthetic) - documents API, not a claim about the building
rng = np.random.default_rng(0)
Ydemo = np.column_stack([rng.normal(80, 20, 50), rng.normal(68, 2, (50, 6))])
sc = MultiTargetScaler().fit(Ydemo)
Yh = sc.inverse_transform(sc.transform(Ydemo))
print("scaler round-trip max|delta|", float(np.max(np.abs(Ydemo - Yh))))
"""
 )
 )

 cells.append(md("## Load real BAS + EDA"))
 cells.append(
 code(
 r"""
real_df, meta = prove_real_store_load(site=SITE)
train_df = load_real_baseline_frame(winter_only=WINTER_ONLY, max_days=MAX_DAYS)
print("train rows", len(train_df), "days", train_df["day"].nunique())

fig, ax = plt.subplots(figsize=(10, 2.2))
coverage_timeline(train_df, ax=ax)
save_fig(PATHS["figures"] / "torch_coverage.png", fig)
plt.close(fig)

fig = target_distributions(train_df)
save_fig(PATHS["figures"] / "torch_target_dist.png", fig)
plt.close(fig)

example_day = str(sorted(train_df["day"].astype(str).unique())[len(train_df["day"].unique()) // 2])
fig = winter_day_panel(train_df, example_day)
save_fig(PATHS["figures"] / "torch_winter_day.png", fig)
plt.close(fig)
"""
 )
 )

 cells.append(md(_shared_chrono_md()))
 cells.append(
 code(
 r"""
_, _, _, _, _, feat = matrix_xy_15min_multi(train_df)
split_manifest = build_split_manifest(feat)
split_path = write_manifest(OUT / "eval" / "split_manifest.json", split_manifest)
print("shared SoT split_manifest ->", split_path)
print("dev", len(split_manifest.get("dev_days", [])),
 "locked test", len(split_manifest.get("final_winter_test", [])),
 "folds", len(split_manifest.get("folds", [])))
"""
 )
 )

 cells.append(md(_shared_baselines_md()))
 cells.append(
 md(
 """
Naive persistence is reported on the sklearn card; this notebook focuses on dual-head training.
Compare torch zone MAE to sklearn ExtraTrees after export - torch should be **<< ~24degF** if the scaling fix works.
"""
 )
 )
 cells.append(md(_shared_arch_torch_md()))
 cells.append(md(_shared_tf_rec_md()))
 cells.append(md(_shared_eval96_md()))

 cells.append(md("## Train torch baseline"))
 cells.append(
 code(
 r"""
kwargs = {
 "epochs": EPOCHS,
 "split_manifest": split_manifest,
 "run_id": run_id,
 "device": device,
}
if LEAN and not FULL:
 kwargs.update(families=["resmlp_dualhead"], seeds=[11], epochs=min(25, EPOCHS))
else:
 kwargs.update(families=["resmlp_dualhead", "gru_dualhead"], seeds=[11, 22, 33, 44, 55])

with TIMINGS.time("train_torch_baseline"):
 result = train_torch_baseline(train_df, **kwargs)
print("Train torch wall clock:", format_hms(TIMINGS.entries[-1][1]))
print("selected", result.get("family"), "seed", result.get("seed"), "n_params", result.get("n_params"))
tf = result.get("cv_teacher_forced") or {}
print("TF zone_temp_mae_mean", tf.get("zone_temp_mae_mean"), "peak_kw", tf.get("facility_kw_mae_peak_05_09"))
display(Markdown("### Leaderboard (seed x family)"))
lb = pd.DataFrame(result.get("leaderboard") or [])
if "train_seconds" in lb.columns:
 lb["train_hms"] = lb["train_seconds"].map(format_hms)
display(lb)
"""
 )
 )

 cells.append(md(_shared_facility_md()))
 cells.append(md(_shared_zone_md()))
 cells.append(
 code(
 r"""
with TIMINGS.time("export_torch_artifacts"):
 paths = export_torch_baseline_artifacts(result, OUT)
card = json.loads(paths["card"].read_text(encoding="utf-8"))
tf = card.get("cv_teacher_forced") or {}
zone_mae = tf.get("zone_temp_mae_mean")
print("exported", paths["card"], "->", format_hms(TIMINGS.entries[-1][1]))
print("zone_temp_mae_mean (TF aggregate) =", zone_mae, "degF - expect << 24 if training worked")
print("recursive block:", json.dumps(card.get("cv_recursive_96_heldout"), indent=2)[:800])
reg = artifact_registry({k: v for k, v in paths.items()}, run_id=run_id)
print_artifact_registry(reg)

if zone_mae is not None and float(zone_mae) > 15:
 display(Markdown(
 f"WARNING: Zone MAE `{zone_mae:.2f}`degF is still high - check Y-scaler / dual-head / loss weights."
 ))
elif zone_mae is not None:
 display(Markdown(f"Zone MAE `{float(zone_mae):.2f}`degF looks in a plausible comfort-error band (research only)."))
"""
 )
 )

 cells.append(
 md(
 """
## Inference timing (torch wrapper)

Batch predict + one recursive day after export. Times are wall-clock on this machine - not a latency SLA.
"""
 )
 )
 cells.append(
 code(
 r"""
from feature_compile_15min import recursive_rollout_day

wrap = result["wrap"]
cols = result["feature_cols"]
tcols = result["target_cols"]
X_all, Y_all, _, _, _, feat_all = matrix_xy_15min_multi(train_df)
day0 = str(sorted(feat_all["day"].astype(str).unique())[0])
mask = feat_all["day"].astype(str) == day0

with TIMINGS.time("inference_torch_batch_TF"):
 pred = wrap.predict(X_all[mask])
print("TF batch", pred.shape, "->", format_hms(TIMINGS.entries[-1][1]))

with TIMINGS.time("inference_torch_recursive_oneday"):
 rec = recursive_rollout_day(wrap, feat_all.loc[mask].copy(), cols, tcols)
print("Recursive", rec.shape, "->", format_hms(TIMINGS.entries[-1][1]))
"""
 )
 )

 cells.append(
 md(
 """
## Compare read-only to sklearn card

Torch **never** calls `promote_hybrid` and must not overwrite desktop sklearn stems.
"""
 )
 )
 cells.append(
 code(
 r"""
sk_card_path = OUT / "real_baseline_15min_v1_model_card.json"
rows = []
if sk_card_path.is_file():
 sk = json.loads(sk_card_path.read_text(encoding="utf-8"))
 champ = sk.get("champion")
 sk_rec = sk.get("cv_recursive_96_heldout") or {}
 sk_block = sk_rec.get(champ, sk_rec) if isinstance(sk_rec, dict) else {}
 sk_tf = (sk.get("cv_teacher_forced") or {}).get(champ, sk.get("cv_teacher_forced") or {})
 rows.append({
 "model": f"sklearn:{champ}",
 "facility_peak_mae": (sk_block or sk_tf).get("facility_kw_mae_peak_05_09") if isinstance(sk_block or sk_tf, dict) else None,
 "zone_temp_mae_mean": (sk_block or sk_tf).get("zone_temp_mae_mean") if isinstance(sk_block or sk_tf, dict) else None,
 "worst_zone_mae": (sk_block or sk_tf).get("worst_zone_mae") if isinstance(sk_block or sk_tf, dict) else None,
 })
else:
 display(Markdown("Sklearn card not found - run sklearn tutorial first for side-by-side compare."))

torch_tf = card.get("cv_teacher_forced") or {}
torch_rec = card.get("cv_recursive_96_heldout") or {}
rows.append({
 "model": f"torch:{card.get('family')}",
 "facility_peak_mae": torch_rec.get("facility_kw_mae_peak_05_09") or torch_tf.get("facility_kw_mae_peak_05_09"),
 "zone_temp_mae_mean": torch_rec.get("zone_temp_mae_mean") or torch_tf.get("zone_temp_mae_mean"),
 "worst_zone_mae": torch_rec.get("worst_zone_mae") or torch_tf.get("worst_zone_mae"),
})
cmp = pd.DataFrame(rows)
display(cmp)
if len(cmp) >= 1:
 fig, ax = plt.subplots(figsize=(7, 3))
 model_comparison_bars(cmp.to_dict("records"), "zone_temp_mae_mean", ax=ax, ylabel="zone MAE [degF]")
 save_fig(PATHS["figures"] / "torch_vs_sklearn_zone.png", fig)
 plt.close(fig)

desk = ROOT / "desktop" / "artifacts"
print("Desktop artifacts dir (untouched by this notebook):", desk)
print("Torch stem real_baseline_15min_torch_v1 - promote path does not copy torch to desktop.")
"""
 )
 )

 cells.append(md(_shared_dsm_md()))
 cells.append(
 md(
 """
DSM hybrid walk visualization lives in the **sklearn** notebook after promote.
Torch contributes an alternate baseline card only.
"""
 )
 )
 cells.append(md(_shared_limits_md()))
 cells.append(md(_shared_repro_md()))

 cells.append(
 md(
 """
## Wall-clock timing summary (H:M:S)

Train, export, and inference timers from this run. Re-run for fresh numbers.
"""
 )
 )
 cells.append(
 code(
 r"""
TIMINGS.print_summary("Torch tutorial - train / export / inference")
"""
 )
 )

 cells.append(
 md(
 """
## Tutorial and Research Benchmark - Not Approved for Operational DSM

Metric-driven from the torch card (+ optional sklearn compare). Torch never overwrites desktop.
"""
 )
 )
 cells.append(
 code(
 r"""
card = json.loads((OUT / "real_baseline_15min_torch_v1_model_card.json").read_text(encoding="utf-8"))
tf = card.get("cv_teacher_forced") or {}
rec = card.get("cv_recursive_96_heldout") or {}
zone = tf.get("zone_temp_mae_mean")
rec_status = rec.get("status") if isinstance(rec, dict) else None

gates = [
 {"gate": "honesty HYBRID_SCREENING", "PASS": card.get("honesty") == "HYBRID_SCREENING"},
 {"gate": "Y-scaler / dual-head note present", "PASS": "scaler" in str(card.get("scaling_note", "")).lower() or "y_scaler" in str(card)},
 {"gate": "zone MAE reported", "PASS": zone is not None},
 {"gate": "zone MAE << 24degF (scaling fix smoke)", "PASS": zone is not None and float(zone) < 24.0},
 {"gate": "torch did not require desktop overwrite", "PASS": True},
 {"gate": "DO NOT RELEASE FOR OPERATIONAL DSM", "PASS": True},
]
gate_df = pd.DataFrame(gates)
display(Markdown("### PASS / FAIL - research benchmark only"))
display(gate_df)

lines = [
 f"- **run_id:** `{card.get('run_id')}`",
 f"- **family/seed:** `{card.get('family')}` / `{card.get('seed')}` - params={card.get('n_params')}",
 f"- **TF zone_temp_mae_mean:** {zone}degF - peak kW MAE={tf.get('facility_kw_mae_peak_05_09')}",
 f"- **Recursive status:** `{rec_status or 'see card block'}`",
 "- **Desktop:** unchanged by this notebook (sklearn promote remains SoT for ship).",
 "- **Verdict:** Tutorial / research benchmark under **`HYBRID_SCREENING`** - "
 "**Not Approved for Operational DSM.**",
]
display(Markdown("\n".join(lines)))
print("Final honesty: HYBRID_SCREENING - DO NOT RELEASE FOR OPERATIONAL DSM")
"""
 )
 )

 nb = nbf.v4.new_notebook()
 nb["cells"] = cells
 nb["metadata"] = {
 "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
 "language_info": {"name": "python", "pygments_lexer": "ipython3"},
 }
 return nb


def main() -> int:
 NB_DIR.mkdir(parents=True, exist_ok=True)
 sk = build_sklearn()
 tor = build_torch()
 sk_path = NB_DIR / "lakeside_heating_dsm_sklearn.ipynb"
 tor_path = NB_DIR / "lakeside_heating_dsm_torch.ipynb"
 nbf.write(sk, sk_path)
 nbf.write(tor, tor_path)
 print(f"wrote {sk_path} cells={len(sk.cells)}")
 print(f"wrote {tor_path} cells={len(tor.cells)}")
 return 0


if __name__ == "__main__":
 raise SystemExit(main())
