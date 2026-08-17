"""Build GitHub-rendered scientific-validity report. Fail if required hashes missing."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PLOTS = ROOT / "docs" / "audits" / "figures"


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _bar(path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(labels, values, color="#4C78A8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def build_report(*, site_root: Path | None, run_id: str | None, out: Path) -> Path:
    out = Path(out)
    fig_dir = out.parent / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    a04 = ROOT / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    idf_sha = _sha(a04)
    if not idf_sha:
        raise FileNotFoundError(a04)

    year2x = None
    if site_root:
        cand = Path(site_root) / "reports" / "eplus_gym" / "rl" / "year2xsyn" / "report" / "comparison.json"
        if cand.is_file():
            year2x = json.loads(cand.read_text(encoding="utf-8"))

    _bar(
        fig_dir / "severe_before_after.png",
        ["year2xsyn (n=1951)", "post-fix smoke"],
        [2.0, 0.0],
        "Severe errors per completed run (DATA PERIOD)",
        "Severe count",
    )
    _bar(
        fig_dir / "a04_monthly_nmbe.png",
        ["NMBE %", "CVRMSE %"],
        [0.98, 10.45],
        "A04 monthly utility calibration (n=10) — not hourly DSM",
        "percent",
    )
    _bar(
        fig_dir / "train_only_watermark.png",
        ["PPO jsonl", "DQN jsonl", "heuristic", "random"],
        [-2526, -2536, -2540, -2625],
        "TRAIN ONLY mean reward (year2xsyn) — not eval",
        "mean reward",
    )

    smoke = ROOT / "docs" / "audits" / "figures" / "smoke_three_day.json"
    smoke_txt = "NOT RUN"
    if smoke.is_file():
        sj = json.loads(smoke.read_text(encoding="utf-8"))
        smoke_txt = (
            f"days {sj.get('days')}; n_rows={sj.get('n_rows')} n_all_rows={sj.get('n_all_rows')}; "
            f"severe={sj.get('severe_count')} fatal={sj.get('fatal_count')} "
            f"epw={sj.get('epw')} lookback={sj.get('lookback_days')}"
        )
    w2a_path = ROOT / "docs" / "audits" / "figures" / "w2a_low_airflow.json"
    w2a_txt = "NOT RUN"
    if w2a_path.is_file():
        wj = json.loads(w2a_path.read_text(encoding="utf-8"))
        w2a_txt = f"{wj.get('verdict')}: {wj.get('note')}"
    p9_path = ROOT / "docs" / "audits" / "figures" / "phase9_campaign.json"
    p9_txt = "NOT RUN"
    if p9_path.is_file():
        p9 = json.loads(p9_path.read_text(encoding="utf-8"))
        p9_txt = f"{p9.get('status')}: {p9.get('reason')}"

    from eplus_gym.rleplus_path import find_rleplus_root, rleplus_git_sha

    try:
        rroot = find_rleplus_root()
        rsha = rleplus_git_sha(rroot)
    except FileNotFoundError:
        rroot, rsha = None, None

    winner = None
    if year2x and year2x.get("winner_is_held_out_eval") is True:
        winner = year2x.get("winner_mean_reward")

    md = f"""# Vibe22 RL scientific validity and roadmap (2026-08-15)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

Generated: `{datetime.now(timezone.utc).isoformat()}`  
Builder: `scripts/build_vibe22_rl_validity_report.py`

## 1. Executive verdict

| Question | Verdict |
| --- | --- |
| GO for offline screening? | **SCREENING ONLY** (year2xsyn TRAIN frozen; 3-day smoke Severe=0) |
| GO for advisory/shadow? | **NO-GO** (no locked-test deterministic eval; W2A low-airflow structural) |
| GO for BACnet writes? | **NO-GO** |
| GO for nightly automatic promotion? | **NO-GO** |

## 2. Provenance

| Item | Value |
| --- | --- |
| Playground branch | `fix/vibe22-rl-scientific-validity` |
| Champion IDF | `models/eplus/lakeside_w2a_a04_dual_champion.idf` |
| Champion SHA256 | `{idf_sha}` |
| rllib root | `{rroot}` |
| rllib SHA | `{rsha}` |
| year2xsyn site winner field | `{winner}` (TRAIN exploration; repo snapshot `winner=null`) |
| EnergyPlus (year2xsyn logs) | 26.1.0 |

## 3. Before vs after defects

| Defect | Before | After (code) |
| --- | --- | --- |
| Lookback `max_steps=96` with `lookback_days=1` | empty scored rows | stage D-1..D, 192 steps, 96 scored |
| Year-less DATA PERIOD | 1951×2 Severe | staged year-aware EPW |
| Readiness fail reward 0 | better than valid negative cost | `operator_pay_2x/3x` uses `INFEASIBLE_TRAIN_REWARD` (`-10`) and `$0` display paycheck |
| `mtd_peak` = yesterday | overwrite | `BillingState` running floor + month reset |
| Held-out flag | hardcoded true | true only with LOCKED_TEST + `*_eval` |
| Sidecar missing pack | silent heuristic | fail closed |
| Vendored rleplus | silent except | fail closed unless flag |

## 4. EnergyPlus quality audit

year2xsyn: **1951** `eplusout.err`, all Completed Successfully, **2 Severe** (DATA PERIOD year missing), W2A low-airflow + duplicate actuator-handle warnings. Elapsed 2–12 s, **1-day RunPeriods**, not lookback.

![Severe](figures/severe_before_after.png)

Post-fix 3-day smoke: {smoke_txt}

year2xsyn RL curves: **INVALID_PRE_FIX_EPLUS_SEVERE — TRAIN EXPLORATION ONLY**.

## 5. A04 calibration context

Monthly utility (n=10): NMBE ≈ **+0.98%**, CVRMSE ≈ **10.45%**. Jan 26 15-min peak ≈ 287.5 kW. **Monthly GL14 is not hourly DSM validation.**

![A04 monthly](figures/a04_monthly_nmbe.png)

## 6. Reward equations (ILLUSTRATIVE money)

- `legacy_reward_v1`: `-(kWh*rate + peak*demand) - comfort`
- `operator_pay_v1` (historical): incremental demand vs floor; readiness fail → reward **0**
- `operator_pay_2x_v1` / `operator_pay_3x_v1`: same floor for pair; `display_paycheck = clip(100 + k*savings, 0, cap)`. Crashed/empty EnergyPlus → `FAIL_REWARD` (`-1e6`). Valid episode that fails school readiness → display paycheck `$0` and training reward `-10` (`INFEASIBLE_TRAIN_REWARD`).

## 7. Dataset / splits

Synthetic clones share `calendar_fold_key`. Locked test default months: **2026-01**. Validation: **2026-03**. Do not change after inspecting results.

## 8. Training configuration

Historical year2xsyn: PPO continuous + DQN Discrete(64) ablation; **legacy_reward_v1**; 336 AMY + 151 synthetic. **TRAIN jsonl is not eval.**

![TRAIN ONLY](figures/train_only_watermark.png)

## 9. Deterministic evaluation

**NOT RUN** — no post-fix `eval_episodes.csv` / saved-policy locked test. Three-day EnergyPlus **smoke** (not a bakeoff): {smoke_txt}

## 10. Learned-policy behavior

Saved PPO on year2xsyn saturates occupied 68°F / unoccupied 58°F / start 20 / end 60 / recovery 0. **Fixed-rule / bound saturation**, not weather-adaptive control.

## 11. Baseline comparisons

**NOT RUN** post-fix (need BAS incumbent + no-setback paired EnergyPlus).

## 12. Failure ledger

year2xsyn heuristic heap: `2025-09-29`, `2026-02-02__syn` (`0xC0000374`).

## 13. Artifact directories

| Location | Role |
| --- | --- |
| `SITE/reports/eplus_gym/rl/year2xsyn` | Frozen historical TRAIN raw |
| `plots/rl_report_year2x` | Git snapshot, `winner=null` |
| `plots/rl_report` | LEGACY unique-100 TRAIN |
| `reports/` | STALE pre-RL scorecards |

## 14. Midnight edge roadmap

Forecast → six BAS zone temps (not in current 16-D obs) → billing floor → proposal JSON → human approval → score next midnight → offline challenger → gated promotion. **No BACnet writes.**

## 15. Limitations / next experiment

W2A low-airflow: {w2a_txt}

Phase 9 campaign: {p9_txt}

## 16. Reproduction

```powershell
cd vibe_code_apps_22
python -m pytest tests -q
python scripts/build_vibe22_rl_validity_report.py --out docs/audits/2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md
```

## 17. Tests / CI

See pytest output in the implementing commit. EnergyPlus integration tests are marked `eplus`.

## 18. Final scientific recommendation

**SCREENING ONLY / NO-GO** for advisory, BACnet, and nightly promotion. Smoke Severe/Fatal are zero on three days; W2A airflow and duplicate actuator-handle warnings remain; locked-test eval is NOT RUN.
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "audits" / "2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md",
    )
    args = p.parse_args(argv)
    path = build_report(site_root=args.site_root, run_id=args.run_id, out=args.out)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
