"""Publish docs/results/weather_trigger_continuous pack."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.rl.two_month_cost import build_flat_cost_table, build_tou_cost_table
from eplus_gym.rl.two_month_provenance import load_actual_utility_evidence
from eplus_gym.rl.weather_trigger_figures import generate_weather_figures
from eplus_gym.rl.weather_trigger_metrics import (
    STRATEGY_LABELS,
    build_summary_table,
    peak_cap_feasibility,
    peak_first_sensitivity,
    research_conclusion,
)
from eplus_gym.rl.weather_trigger_select import load_weather_trigger_contract

PUBLIC_LABELS = [
    "SIMULATION-ONLY RESEARCH",
    "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
    "ILLUSTRATIVE COSTS",
    "RETROSPECTIVE_WEATHER_POLICY_SCREEN",
    "NO BACNET COMMAND AUTHORITY",
]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def publish_weather_pack(
    *,
    app_root: Path,
    site: Path,
    site_run_dir: Path,
    results: Mapping[str, Mapping[str, Any]],
    compute_facts: Mapping[str, Any] | None = None,
) -> Path:
    out = Path(app_root) / "docs" / "results" / "weather_trigger_continuous"
    out.mkdir(parents=True, exist_ok=True)
    contract = load_weather_trigger_contract(app_root)
    summaries = build_summary_table(results)
    flat = build_flat_cost_table(results)
    tou = build_tou_cost_table(results)
    peak_first = peak_first_sensitivity(results, tie_kw=float(contract.get("peak_first_tie_kw") or 1.0))
    caps = peak_cap_feasibility(results)
    invalid = any(int(p.get("n_intervals") or 0) != 5952 for p in results.values())
    conclusion = research_conclusion(results=results, invalid=invalid)

    trigger_rows: list[dict[str, Any]] = []
    for strategy, payload in results.items():
        for tl in payload.get("trigger_log") or []:
            row = {"strategy": strategy, **{k: v for k, v in tl.items() if k != "hourly_oat_f"}}
            oats = tl.get("hourly_oat_f") or []
            for i, v in enumerate(oats):
                row[f"oat_f_h{i:02d}"] = round(float(v), 4)
            trigger_rows.append(row)
        if not payload.get("trigger_log"):
            for d in payload.get("daily") or []:
                if "selected_mode" in d or "continuous_day" in d:
                    trigger_rows.append(
                        {
                            "strategy": strategy,
                            "day": d.get("day"),
                            "selected_mode": d.get("selected_mode"),
                            "continuous_day": d.get("continuous_day"),
                            "trigger_reason": d.get("trigger_reason"),
                        }
                    )

    utility = load_actual_utility_evidence(site)
    util_rows = [
        {
            "strategy": "actual_utility_cs351075",
            "public_label": STRATEGY_LABELS["actual_utility_cs351075"],
            "period": "2025-12",
            "kwh": utility["dec_2025"]["kwh"],
            "billed_demand_kw": utility["dec_2025"]["billed_demand_kw"],
            "actual_total_bill_usd": utility["dec_2025"]["actual_total_bill_usd"],
            "ranking_eligible": False,
            "reference_only": True,
        },
        {
            "strategy": "actual_utility_cs351075",
            "public_label": STRATEGY_LABELS["actual_utility_cs351075"],
            "period": "2026-01",
            "kwh": utility["jan_2026"]["kwh"],
            "billed_demand_kw": utility["jan_2026"]["billed_demand_kw"],
            "actual_total_bill_usd": utility["jan_2026"]["actual_total_bill_usd"],
            "ranking_eligible": False,
            "reference_only": True,
        },
    ]

    compute_facts = compute_facts or {}
    compute_rows = [
        {
            "category": "weather_trigger_replay_wall",
            "wall_s": sum(float(p.get("elapsed_s") or 0) for s, p in results.items() if s.startswith(("ALWAYS_", "COLD_"))),
            "note": "sum of LIVE weather-policy walls",
        },
        {
            "category": "nightly_exhaustive_candidate_compute",
            "wall_s": compute_facts.get("nightly_exhaustive_s", 320.8),
            "note": "sequential exhaustive candidate compute time",
        },
        {
            "category": "rl_offline_train_primary",
            "wall_s": compute_facts.get("rl_train_primary_s"),
            "note": "recorded PRIMARY training wall",
        },
        {
            "category": "rl_inference_ppo_p50",
            "wall_s": compute_facts.get("ppo_inference_s"),
            "note": "p50 predict",
        },
    ]

    _write_csv(out / "strategy_summary.csv", summaries)
    _write_csv(out / "flat_cost_table.csv", flat)
    _write_csv(out / "tou_cost_table.csv", tou)
    _write_csv(out / "peak_cap_feasibility.csv", caps)
    _write_csv(out / "daily_trigger_log.csv", trigger_rows)
    _write_csv(out / "actual_utility_reference.csv", util_rows)
    _write_csv(out / "compute_comparison.csv", compute_rows)
    (out / "peak_first_sensitivity.json").write_text(json.dumps(peak_first, indent=2), encoding="utf-8")
    (out / "research_conclusion.json").write_text(json.dumps(conclusion, indent=2), encoding="utf-8")
    (out / "contract_snapshot.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    idf_sha = next((p.get("idf_sha256") for p in results.values() if p.get("idf_sha256")), None)
    epw_sha = next((p.get("epw_sha256") for p in results.values() if p.get("epw_sha256")), None)
    n_eplus = sum(int(p.get("n_process_starts") or 0) for s, p in results.items() if s.startswith(("ALWAYS_", "COLD_")))

    manifest = {
        "schema": "vibe22.weather_trigger_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_run_dir": str(site_run_dir),
        "public_labels": PUBLIC_LABELS,
        "weather_label": "RETROSPECTIVE_WEATHER_POLICY_SCREEN",
        "strategies": sorted(results.keys()),
        "n_strategies": len(results),
        "n_energyplus_processes_weather_policies": n_eplus,
        "intervals_per_strategy": 5952,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "research_conclusion": conclusion,
        "peak_first_sensitivity": peak_first,
        "bacnet_commands": 0,
        "simulation_training_ready": False,
        "operational_dsm_ready": False,
        "trajectory_hashes": {s: p.get("trajectory_hash") for s, p in results.items()},
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    generate_weather_figures(
        out_dir=out,
        summaries=summaries,
        results=results,
        daily_triggers=trigger_rows,
        compute_rows=compute_rows,
    )

    labels = "\n".join(f"- `{x}`" for x in PUBLIC_LABELS)
    best_econ = conclusion.get("best_economic_strategy")
    lowest_peak = conclusion.get("lowest_peak_strategy") or (peak_first.get("selected"))
    readme = f"""# Weather-triggered continuous-conditioning grid experiment

> Realized EPW outdoor temperatures drive retrospective midnight-only daily policy selection
> (`RETROSPECTIVE_WEATHER_POLICY_SCREEN`). Modeled costs are illustrative. Continuous 68/74
> actuates heating at 68°F all day; cooling remains fixed ~74/85°F thermostatic schedules.

## Public labels

{labels}

## Research conclusion

**`{conclusion.get("verdict")}`** — no operational winner.

- Best economic strategy (illustrative FLAT): `{best_econ}`
- Lowest-peak / peak-first sensitivity: `{lowest_peak}`
- `SIMULATION_TRAINING_READY`: false
- `OPERATIONAL_DSM_READY`: false
- BACnet command authority: **0**

## Scope

- Scored days: 2025-12-01 … 2026-01-31 (62 days, 5,952 intervals per strategy)
- Weather policies LIVE: 9 continuous EnergyPlus processes
- Reference arms imported from two-month replay (not re-run)
- Primary tariff: FLAT_PLUS_DEMAND; secondary TOU re-score

## Artifacts

| File | Role |
| --- | --- |
| `strategy_summary.csv` | P7 metrics per strategy |
| `daily_trigger_log.csv` | Daily decision + 24 hourly OAT °F |
| `flat_cost_table.csv` / `tou_cost_table.csv` | Illustrative costs |
| `peak_first_sensitivity.json` | PEAK_FIRST_RESEARCH_SENSITIVITY |
| `peak_cap_feasibility.csv` | 260/250/240/230 kW caps |
| `research_conclusion.json` | Single research verdict |
| `figures/` | 10 PNG+SVG plots |

## Honesty

- Do not describe illustrative dollars as verified savings.
- Do not claim PPO/DQN were trained on weather-trigger logic.
- Mild/weekend nightly optional days remain NOT_RUN (separate pack).
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    return out
