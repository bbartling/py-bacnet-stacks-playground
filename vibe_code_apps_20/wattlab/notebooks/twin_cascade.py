"""Run measure EnergyPlus cascade on a G14-calibrated Twin (no baseline schedule patch)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.energyplus.manifest import build_run_manifest, write_run_manifest
from wattlab.energyplus.patches.hourly_outputs import apply_monthly_energy_tables
from wattlab.energyplus.results import annual_from_output_dir, build_result_record, savings_by_measure
from wattlab.ecm.catalog import load_catalog


def _resolve_epw(
    twin_dir: Path, profile: dict[str, Any] | None
) -> tuple[Path, dict[str, Any]]:
    """Return (epw_path, weather_suitability). Never silently substitute without a stamp."""
    profile = profile or {}
    ep = profile.get("energyplus") or {}
    for key in ("epw", "weather_epw", "weather"):
        raw = ep.get(key) or profile.get(key)
        if raw:
            p = Path(str(raw))
            if p.is_file():
                return p, {
                    "mode": "ACTUAL_YEAR_CALIBRATION",
                    "reason": f"profile/{key}",
                }
    for name in ("Weather.epw", "weather.epw", "amy.epw"):
        p = twin_dir / name
        if p.is_file():
            return p, {
                "mode": "ACTUAL_YEAR_CALIBRATION",
                "reason": f"twin_dir/{name}",
            }
    default = Path("/app/examples/weather/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    if default.is_file():
        return default, {
            "mode": "SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY",
            "reason": "Twin/profile omitted EPW; using bundled Chicago TMY3 for screening only",
        }
    raise FileNotFoundError(
        f"No EPW beside {twin_dir} and no profile energyplus.epw — cannot simulate measures"
    )


def _measure_row(measure_id: str) -> dict[str, Any]:
    """Map canonical catalog.yaml entry → easy-button measure dict with idf_patch."""
    entry = load_catalog().get(measure_id)
    if entry is None:
        raise KeyError(f"Unknown measure_id {measure_id!r} (not in measures/catalog.yaml)")
    patch = entry.energyplus_patch
    return {
        "measure_id": measure_id,
        "title": entry.display_name,
        "idf_patch": {"name": patch, "params": {}} if patch else {},
        "review_status": "approved",
        "status": entry.status,
    }


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
    Failed simulations raise — never invent savings from empty output dirs.
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
    epw, weather_suitability = _resolve_epw(twin_dir, profile)
    elec_rate, gas_rate = _rates(profile)

    run_id = twin_dir.name
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = Path(out_dir) if out_dir else twin_dir / f"ecm_cascade_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    measures = [_measure_row(mid) for mid in measure_ids]
    steps: list[dict[str, Any]] = [
        {
            "step": "baseline",
            "model_idf": str(model),
            "epw": str(epw),
            "weather_suitability": weather_suitability,
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
            "weather_suitability": weather_suitability,
            "honesty": "Calibrated baseline — no fan_avail_continuous screening patch",
        }

    prepped = run_dir / "baseline_prepped.idf"
    apply_monthly_energy_tables(model, prepped)
    baseline_idf = run_dir / "baseline.idf"
    shutil.copy2(prepped, baseline_idf)

    patch_names: list[str] = ["monthly_energy_tables"]
    for m in measures:
        pname = ((m.get("idf_patch") or {}).get("name")) or ""
        if pname:
            patch_names.append(pname)

    write_run_manifest(
        run_dir,
        build_run_manifest(
            run_id=f"{run_id}_ecm_cascade",
            run_dir=run_dir,
            idf_path=baseline_idf,
            epw_path=epw,
            patches=patch_names,
            weather_suitability=weather_suitability,
            status="RUNNING",
            started_at=started_at,
            extra={"calibrated_twin_baseline": True, "twin_run": run_id},
        ),
    )

    base_out = run_dir / "sim_baseline"
    base_result = simulate(baseline_idf, epw, base_out)
    if not base_result.get("ok"):
        write_run_manifest(
            run_dir,
            build_run_manifest(
                run_id=f"{run_id}_ecm_cascade",
                run_dir=run_dir,
                idf_path=baseline_idf,
                epw_path=epw,
                patches=patch_names,
                weather_suitability=weather_suitability,
                status="NEEDS_INPUT",
                started_at=started_at,
                extra={
                    "error": "baseline_simulate_failed",
                    "sim": base_result,
                },
            ),
        )
        raise RuntimeError(
            f"Baseline EnergyPlus run failed: {base_result.get('stderr_tail') or base_result}"
        )

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
        sim_result = simulate(patched, epw, out)
        if not sim_result.get("ok"):
            write_run_manifest(
                run_dir,
                build_run_manifest(
                    run_id=f"{run_id}_ecm_cascade",
                    run_dir=run_dir,
                    idf_path=patched,
                    epw_path=epw,
                    patches=patch_names,
                    weather_suitability=weather_suitability,
                    status="NEEDS_INPUT",
                    started_at=started_at,
                    extra={
                        "error": f"simulate_failed:{mid}",
                        "sim": sim_result,
                    },
                ),
            )
            raise RuntimeError(
                f"EnergyPlus run failed for {mid}: "
                f"{sim_result.get('stderr_tail') or sim_result}"
            )
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
                extra_flags=[*(meta.get("flags") or []), "openfdd_wattlab"],
            )
        )

    savings = savings_by_measure(records)
    report = {
        "run_id": run_id,
        "twin_run": run_id,
        "calibrated_baseline": True,
        "baseline_idf": str(baseline_idf),
        "epw": str(epw),
        "weather_suitability": weather_suitability,
        "measure_ids": measure_ids,
        "savings_by_measure": savings,
        "records": records,
    }
    report_path = run_dir / "wattlab_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    write_run_manifest(
        run_dir,
        build_run_manifest(
            run_id=f"{run_id}_ecm_cascade",
            run_dir=run_dir,
            idf_path=baseline_idf,
            epw_path=epw,
            patches=patch_names,
            weather_suitability=weather_suitability,
            status="SUCCESS",
            started_at=started_at,
            extra={"calibrated_twin_baseline": True, "twin_run": run_id},
        ),
    )

    twin_report = twin_dir / "wattlab_report.json"
    merged: dict[str, Any] = {}
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
            "weather_suitability": weather_suitability,
        }
    )
    twin_report.write_text(json.dumps(merged, indent=2, default=str) + "\n", encoding="utf-8")
    report["twin_report_path"] = str(twin_report)
    report["out_dir"] = str(run_dir)
    report["report_path"] = str(report_path)
    return report
