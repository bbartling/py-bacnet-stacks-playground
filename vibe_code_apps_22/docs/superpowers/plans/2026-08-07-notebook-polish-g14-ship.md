# Notebook Polish + G14 Ship Precision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish Lakeside notebooks, emit ASHRAE G14-style NMBE/CV(RMSE) into ship artifacts, wire Rust UI to those artifacts (champions + ±), then smoke-train, promote, and launch desktop.

**Architecture:** Artifact-driven fixed ONNX stems; promote enriches `hybrid_ship_manifest.json` + feature_meta; Rust loads manifest for display metrics; notebooks share a matplotlib theme + metric cards.

**Tech Stack:** Python (sklearn train, promote, nbformat), matplotlib, Rust egui+ort desktop.

## Global Constraints

- Honesty claim remains `HYBRID_SCREENING` only.
- Smoke farm: `VIBE22_ALLOW_SMOKE_PROMOTE=1`; watermark `UNDERPOWERED_SMOKE_FARM`.
- Torch notebook must not overwrite desktop ship stems.
- ± band = screening precision from held-out peak MAE; not a CI; not operational G14 pass.
- G14 monthly reference shown as context: |NMBE|<=5%, CV(RMSE)<=15% (calibrated monthly).
- ASCII-safe notebook prose (no mojibake via PowerShell Set-Content).
- Prefer editing generators then regenerating notebooks.

## File map

| File | Role |
|---|---|
| `ml/metrics_report.py` | Already has nmbe/cv_rmse; used by trainers |
| `ml/train_real_baseline_15min.py` | Add NMBE/CVRMSE to recursive held-out flats |
| `ml/train_eplus_delta_15min.py` | Same for delta arm (kw deltas) |
| `scripts/promote_hybrid_ship.py` | `mv_precision` block + stamp feature_meta |
| `ml/notebook_plots.py` | `apply_notebook_theme`, metric card HTML helper |
| `scripts/_gen_tutorial_notebooks.py` | Theme + cards + tighter markdown |
| `scripts/_gen_load_profile_analysis_nb.py` | Theme + cleaner narrative |
| `desktop/src/hybrid.rs` or new `ship_manifest.rs` | Load/parse ship manifest |
| `desktop/src/main.rs` | Wire precision_pm + metrics from manifest |
| `tests/test_promote_hybrid_gates.py` / new tests | Manifest mv_precision + Rust if feasible |

---

### Task 1: Held-out NMBE / CV(RMSE) in baseline trainer

**Files:** `ml/train_real_baseline_15min.py`, `tests/` (extend or add)

- [ ] Add failing test that recursive day-score / heldout flat includes `facility_kw_cv_rmse` and `facility_kw_nmbe`.
- [ ] Compute via `metrics_report.cv_rmse` / `nmbe` (or inline) on facility series when scoring held-out days; mean across days into flat headlines.
- [ ] Run test green.
- [ ] Commit.

### Task 2: Delta trainer G14-ish headlines

**Files:** `ml/train_eplus_delta_15min.py`, tests

- [ ] Add `cv_rmse_delta_kw` / `nmbe_delta_kw` (or facility-equivalent names) on held-out delta scores.
- [ ] Tests green; commit.

### Task 3: Promote `mv_precision` + stamp meta

**Files:** `scripts/promote_hybrid_ship.py`, `tests/test_promote_hybrid_gates.py`

- [ ] Extend `_heldout_headlines` keys for nmbe/cv_rmse.
- [ ] Build `mv_precision` on ship + walk; set `precision_pm_kw` from baseline `facility_kw_mae_peak_05_09` (fallback MAE).
- [ ] Patch desktop/ml `_feature_meta.json` with `precision_pm_kw`, champion, honesty.
- [ ] Tests assert manifest keys; commit.

### Task 4: Rust loads ship manifest

**Files:** `desktop/src/ship_manifest.rs` (new), `main.rs`, `lib`/`mod` wiring, optional Rust test

- [ ] Deserialize manifest; resolve beside ONNX dirs.
- [ ] On hybrid load success: `precision_pm` from `mv_precision.precision_pm_kw`; metrics_lines with NMBE%, CVRMSE%, MAE±, G14 note, watermark.
- [ ] Banner champions prefer manifest over meta.
- [ ] `cargo test` + `cargo build --release`; commit.

### Task 5: Notebook theme + cards + regen

**Files:** `ml/notebook_plots.py`, generators, notebooks

- [ ] `apply_notebook_theme()`, `metric_cards_html(...)`.
- [ ] Wire into generators (setup cell + post-train/promote display).
- [ ] Regenerate three notebooks; commit.

### Task 6: Execute smoke train + launch desktop

- [ ] Set `LAKESIDE_SITE_ROOT`, `VIBE22_ALLOW_SMOKE_PROMOTE=1`.
- [ ] Run load-profile, sklearn, torch notebooks (or CLI equivalents if notebook kernel blocked).
- [ ] Verify `desktop/artifacts/hybrid_ship_manifest.json` has champions + mv_precision.
- [ ] `cargo run --release` from `desktop/`.
- [ ] Commit any remaining artifact/doc fixes if needed.
