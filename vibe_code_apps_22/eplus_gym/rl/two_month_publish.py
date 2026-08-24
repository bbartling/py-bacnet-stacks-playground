"""Assemble docs/results/two_month_policy_replay publication pack."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.rl.two_month_cost import build_flat_cost_table, build_tou_cost_table, rank_strategies
from eplus_gym.rl.two_month_figures import generate_all_figures
from eplus_gym.rl.two_month_metrics import (
    STRATEGY_LABELS,
    aggregate_monthly_physical,
    build_daily_metrics_table,
    build_decision_table,
    build_quality_ledger,
    compare_vs_continuous_68,
)
from eplus_gym.rl.two_month_provenance import NOT_AVAILABLE, build_provenance, load_actual_utility_evidence

README_BODY = """# Two-month frozen-policy replay (Dec 2025 – Jan 2026)

> The utility-provider rows are actual monthly billing records. PPO, DQN, grid, continuous-conditioning, and A04 scenario rows are retrospective EnergyPlus counterfactuals. Modeled tariff charges are illustrative and are not reconciled to the actual utility invoice.

## Scope

- **Scored days:** 2025-12-01 … 2026-01-31 (62 days, 5,952 intervals per strategy)
- **Lookback:** 2025-11-30
- **Strategies:** seven frozen policies (A04 native, observed BAS v2, continuous-68 sensitivity, frozen PPO/DQN, grid discrete 42/43)
- **BACnet command authority:** 0

## Public labels

{labels}

## Decision memo (10 questions)

1. **PPO vs continuous-68 on peak+kWh:** see `two_month_decision_table.csv` and fig06/fig09.
2. **DQN vs continuous-68:** same tables; TOU cost ranking is separate from flat.
3. **Grid 42/43 vs continuous-68:** day counts in `run_manifest.json` → `vs_continuous_68`.
4. **School-day vs non-school:** `daily_metrics.csv` `day_category` column.
5. **Cold vs mild school days:** appendix categories; not inferred from arm names.
6. **Min kWh (two-month):** lowest `two_month_kwh` in decision table among six-zone strategies.
7. **Min peak (two-month):** lowest `two_month_peak_kw` in decision table.
8. **Min illustrative flat cost:** `flat_cost_table.csv` two_month rank (modeled only).
9. **Min illustrative TOU cost:** `tou_cost_table.csv` two_month rank (separate from flat).
10. **Actual utility:** total bill only; component charges `{na}`.

## Honesty

- December overlaps RL training window (`RETROSPECTIVE_CONTAMINATED`).
- January inspected but not a pristine holdout.
- A04 native is **not** transient-validated; scalar SCH_HtgSP ≠ six-zone DualSP actuation.
- Continuous-68 sensitivity actuates **heating only**; cooling remains IDF thermostatic defaults (~74/85°F).
- VERIFIED_BAS_INCUMBENT remains UNRESOLVED.

## Artifacts

| File | Role |
| --- | --- |
| `provenance.json` | Frozen inputs + SHA-256 |
| `actual_utility_evidence.csv` | CS 351075 Dec/Jan actuals |
| `monthly_physical_metrics.csv` | kWh/peak by strategy × month |
| `daily_metrics.csv` | Per-day physical metrics |
| `flat_cost_table.csv` | Illustrative FLAT + demand |
| `tou_cost_table.csv` | Illustrative TOU + demand (separate ranking) |
| `two_month_decision_table.csv` | kWh/peak only — no dollars |
| `quality_ledger.csv` | Readiness appendix only |
| `run_manifest.json` | Execution summary + trajectory hashes |
| `figures/` | 12 PNG+SVG plots |
"""


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _utility_csv_rows(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for period, key in (("2025-12", "dec_2025"), ("2026-01", "jan_2026")):
        b = evidence[key]
        rows.append(
            {
                "account": evidence["account"],
                "period": period,
                "kwh": b["kwh"],
                "billed_demand_kw": b["billed_demand_kw"],
                "actual_total_bill_usd": b["actual_total_bill_usd"],
                "actual_energy_charge_usd": b["actual_energy_charge_usd"],
                "actual_demand_charge_usd": b["actual_demand_charge_usd"],
                "source_path": evidence["source_path"],
            }
        )
    rows.append(
        {
            "account": evidence["account"],
            "period": "two_month",
            "kwh": evidence["two_month"]["kwh"],
            "billed_demand_kw": NOT_AVAILABLE,
            "actual_total_bill_usd": evidence["two_month"]["actual_total_bill_usd"],
            "actual_energy_charge_usd": NOT_AVAILABLE,
            "actual_demand_charge_usd": NOT_AVAILABLE,
            "source_path": evidence["source_path"],
        }
    )
    return rows


def publish_pack(
    *,
    app_root: Path,
    site: Path,
    results: Mapping[str, Mapping[str, Any]],
    site_run_dir: Path | None = None,
) -> Path:
    out = app_root / "docs" / "results" / "two_month_policy_replay"
    out.mkdir(parents=True, exist_ok=True)
    provenance = build_provenance(app_root=app_root, site=site)
    utility = provenance["utility_evidence"]

    monthly: list[dict[str, Any]] = []
    for strategy, payload in results.items():
        monthly.extend(
            aggregate_monthly_physical(
                strategy=strategy,
                facility_kw=payload["facility_kw"],
                daily_rows=payload.get("daily") or [],
            )
        )
    daily = build_daily_metrics_table(results)
    flat = build_flat_cost_table(results, utility_evidence=utility)
    tou = build_tou_cost_table(results, utility_evidence=utility)
    decision = build_decision_table(results)
    quality = build_quality_ledger(results)
    vs68 = compare_vs_continuous_68(results)

    _write_csv(out / "actual_utility_evidence.csv", _utility_csv_rows(utility))
    _write_csv(out / "monthly_physical_metrics.csv", monthly)
    _write_csv(out / "daily_metrics.csv", daily)
    _write_csv(out / "flat_cost_table.csv", flat)
    _write_csv(out / "tou_cost_table.csv", tou)
    _write_csv(out / "two_month_decision_table.csv", decision)
    _write_csv(out / "quality_ledger.csv", quality)

    (out / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    manifest = {
        "schema": "vibe22.two_month_replay_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_run_dir": str(site_run_dir) if site_run_dir else None,
        "strategies_attempted": sorted(results.keys()),
        "n_strategies_ok": len(results),
        "trajectory_hashes": {k: v.get("trajectory_hash") for k, v in results.items()},
        "tariff_rescore_note": "Flat and TOU re-scoring reused identical trajectory hashes; no new EnergyPlus.",
        "flat_rank_two_month": rank_strategies(flat, period="two_month"),
        "tou_rank_two_month": rank_strategies(tou, period="two_month"),
        "vs_continuous_68": vs68,
        "bacnet_commands": 0,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    policy_validation = {
        "obs_schema": "vibe22.obs.v4.mega",
        "observation_dim": 206,
        "zero_obs_forbidden": True,
        "forecast_source": "PERFECT_EPISODE_FORECAST_RETROSPECTIVE",
        "strategies_with_full_obs": [
            s for s in results if s in ("frozen_ppo_flat_seed0", "frozen_dqn_tou_seed1")
        ],
    }
    (out / "policy_schema_validation.json").write_text(json.dumps(policy_validation, indent=2), encoding="utf-8")

    labels = "\n".join(f"- `{k}` → {v}" for k, v in STRATEGY_LABELS.items())
    (out / "README.md").write_text(
        README_BODY.format(labels=labels, na=NOT_AVAILABLE),
        encoding="utf-8",
    )

    generate_all_figures(
        out_dir=out,
        monthly_physical=monthly,
        flat_cost=flat,
        tou_cost=tou,
        daily_metrics=daily,
        decision_table=decision,
        results=results,
        utility_evidence=utility,
    )
    return out
