"""Run measure EnergyPlus cascade on a G14-calibrated Twin (no baseline schedule patch)."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.energyplus.patches.hourly_outputs import apply_monthly_energy_tables
from wattlab.energyplus.results import annual_from_output_dir, build_result_record, savings_by_measure
from wattlab.measures.measure_sets import load_measure_sets


def _resolve_epw(twin_dir: Path, profile: dict[str, Any] | None) -> Path:
    profile = profile or {}
    ep = profile.get("energyplus") or {}
    for key in ("epw", "weather_epw", "weather"):
        raw = ep.get(key) or profile.get(key)
        if raw:
            p = Path(str(raw))
            if p.is_file():
                return p
    for name in ("Weather.epw", "weather.epw", "amy.epw"):
        p = twin_dir / name
        if p.is_file():
            return p
    # Product default (Chicago TMY3) — conceptual screening when twin omits EPW path
    default = Path("/app/examples/weather/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    if default.is_file():
        return default
    raise FileNotFoundError(
        f"No EPW beside {twin_dir} and no profile energyplus.epw — cannot simulate measures"
    )


def _measure_row(measure_id: str) -> dict[str, Any]:
    catalog = load_measure_sets().get("catalog") or {}
    base = catalog.get(measure_id)
    if not base:
        raise KeyError(f"Unknown measure_id {measure_id!r} (not in measure_sets.json catalog)")
    return deepcopy(base)


def cascade_measures_on_twin(
    twin_run: Path | str,
    measure_ids: list[str],
    *,
    profile: dict[str, Any] | None = None,
    out_dir: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Simulate each measure vs calibrated ``model.idf`` (independent, not chained).

    Writes ``wattlab_report.json`` with ``savings_by_measure`` when EnergyPlus succeeds.
  """
    from wattlab.easy_button import _apply_patch, _rates
    from wattlab.energyplus.mcp import simulate

    twin_dir = Path(twin_run)
    if not twin_dir.is_dir():
        raise FileNotFoundError(twin_dir)
    model = twin_dir / "model.idf"
    if not model.is_file():
        raise FileNotFoundError(f"Missing calibrated model: {model}")

    profile = dict(profile or {})
    epw = _resolve_epw(twin_dir, profile)
    elec_rate, gas_rate = _rates(profile)

    run_id = twin_dir.name
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(out_dir) if out_dir else twin_dir / f"ecm_cascade_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    measures = [_measure_row(mid) for mid in measure_ids]
    steps: list[dict[str, Any]] = [
        {
            "step": "baseline",
            "model_idf": str(model),
            "epw": str(epw),
            "measure_ids": measure_ids,
        }
    ]
    if dry_run:
        for m in measures:
            steps.append(
                {
                    "step": "apply_measure",
                    "measure_id": m["measure_id"],
                    "idf_patch": (m.get("idf_patch") or {}).get("name"),
                }
            )
        return {
            "dry_run": True,
            "twin_run": run_id,
            "out_dir": str(run_dir),
            "steps": steps,
            "honesty": "Calibrated baseline — no fan_avail_continuous screening patch",
        }

    prepped = run_dir / "baseline_prepped.idf"
    apply_monthly_energy_tables(model, prepped)
    baseline_idf = run_dir / "baseline.idf"
    shutil.copy2(prepped, baseline_idf)

    base_out = run_dir / "sim_baseline"
    simulate(baseline_idf, epw, base_out)
    annual = annual_from_output_dir(
        base_out, elec_rate_usd_per_kwh=elec_rate, gas_rate_usd_per_therm=gas_rate
    )
    records: list[dict[str, Any]] = [
        build_result_record(
            run_id=f"{run_id}_baseline",
            measure_id=None,
            idf_path=baseline_idf,
            annual=annual,
            artifacts=[str(base_out / "eplustbl.htm")],
            extra_flags=["calibrated_twin_baseline", "openfdd_wattlab"],
        )
    ]

    for m in measures:
        mid = m["measure_id"]
        pname = ((m.get("idf_patch") or {}).get("name")) or ""
        if not pname:
            records.append(
                build_result_record(
                    run_id=f"{run_id}_{mid}",
                    measure_id=mid,
                    idf_path=baseline_idf,
                    annual=annual,
                    artifacts=[],
                    extra_flags=["no_energyplus_patch"],
                )
            )
            continue
        patched = run_dir / f"{mid}.idf"
        meta = _apply_patch(pname, baseline_idf, patched, m)
        out = run_dir / f"sim_{mid}"
        simulate(patched, epw, out)
        ann = annual_from_output_dir(
            out, elec_rate_usd_per_kwh=elec_rate, gas_rate_usd_per_therm=gas_rate
        )
        records.append(
            build_result_record(
                run_id=f"{run_id}_{mid}",
                measure_id=mid,
                idf_path=patched,
                annual=ann,
                artifacts=[str(out / "eplustbl.htm"), str(patched)],
                extra_flags=list(meta.get("flags") or []) + ["openfdd_wattlab"],
            )
        )

    savings = savings_by_measure(records)
    report = {
        "run_id": run_id,
        "twin_run": run_id,
        "calibrated_baseline": True,
        "baseline_idf": str(baseline_idf),
        "epw": str(epw),
        "measure_ids": measure_ids,
        "savings_by_measure": savings,
        "records": records,
    }
    report_path = run_dir / "wattlab_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Also drop beside twin for notebook sync-from-twin
    twin_report = twin_dir / "wattlab_report.json"
    merged = {}
    if twin_report.is_file():
        try:
            merged = json.loads(twin_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            merged = {}
    merged.update(
        {
            "savings_by_measure": savings,
            "ecm_cascade_dir": str(run_dir),
            "ecm_cascade_at": stamp,
        }
    )
    twin_report.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    report["twin_report_path"] = str(twin_report)
    return report
