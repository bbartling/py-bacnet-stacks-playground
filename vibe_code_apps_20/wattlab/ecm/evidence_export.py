"""Stage-1 ECM simulation evidence + dual-rail engineering Inputs exporter.

Vibe20 owns EnergyPlus / cascade / sizing evidence. Open-FDD owns schemas and
workbook builders — this module emits JSON sidecars Open-FDD can import.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE_SCHEMA_VERSION = "ecm_simulation_evidence_v1"
EVIDENCE_FILENAME = "ecm_simulation_evidence.json"
INPUTS_FILENAME = "ecm_engineering_inputs.json"
INPUTS_SCHEMA_VERSION = "ecm_engineering_inputs_v1"

_NEEDS_ASSUMPTION_NOTE = frozenset(
    {
        "agent_inferred",
        "engineering_assumption",
        "EnergyPlus_derived",
        "synthetic_rehearsal",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def engineering_input(
    *,
    input_id: str,
    display_name: str,
    value: Any,
    unit: str,
    rail: str,
    source_type: str,
    assumption_note: str = "",
    assumption_method: str = "unknown",
    linked_measure_ids: list[str] | None = None,
    confidence: str = "unknown",
    editable: bool = True,
    validation_status: str = "ok",
    source_reference: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """EngineeringInput-like dict (Open-FDD Stage-1 contract shape)."""
    return {
        "input_id": input_id,
        "display_name": display_name,
        "value": value,
        "unit": unit,
        "rail": rail,
        "source_type": source_type,
        "confidence": confidence,
        "editable": editable,
        "validation_status": validation_status,
        "assumption_note": assumption_note,
        "assumption_method": assumption_method,
        "linked_measure_ids": list(linked_measure_ids or []),
        "source_reference": source_reference,
        "notes": notes,
    }


def validate_engineering_inputs(inputs: list[dict[str, Any]]) -> list[str]:
    """Local Stage-1 gate: agent_inferred / estimated hours need assumption_note."""
    issues: list[str] = []
    for inp in inputs:
        if not isinstance(inp, dict):
            issues.append("input entry must be an object")
            continue
        iid = str(inp.get("input_id") or "?")
        source = str(inp.get("source_type") or "")
        note = str(inp.get("assumption_note") or "").strip()
        needs = source in _NEEDS_ASSUMPTION_NOTE
        lid = iid.lower()
        if "hour" in lid or lid.endswith("_flh") or "hours_saved" in lid:
            if source not in ("measured", "human_entered"):
                needs = True
        if needs and not note:
            issues.append(
                f"{iid}: assumption_note required for {source or 'estimated'} / estimated hours"
            )
    return issues


def build_dual_rail_sizing_inputs(
    *,
    ss_fan_hp: float | None = None,
    ep_fan_hp: float | None = None,
    ss_cooling_tons: float | None = None,
    ep_cooling_tons: float | None = None,
    ss_fan_hours: float | None = None,
    ep_fan_hours: float | None = None,
    linked_measure_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """At least one ss_* / ep_* sizing pair plus optional hour rails."""
    linked = list(linked_measure_ids or [])
    inputs: list[dict[str, Any]] = []

    # Prefer provided values; synthetic-friendly defaults keep a dual-rail pair present.
    ss_hp = ss_fan_hp if ss_fan_hp is not None else 80.0
    ep_hp = ep_fan_hp if ep_fan_hp is not None else ss_hp
    inputs.append(
        engineering_input(
            input_id="ss_fan_hp",
            display_name="Fan power (spreadsheet)",
            value=ss_hp,
            unit="hp",
            rail="spreadsheet",
            source_type="engineering_assumption" if ss_fan_hp is None else "nameplate",
            assumption_note=(
                "Screening fan HP for ESCO formulas; not a field-verified nameplate."
                if ss_fan_hp is None
                else "Operator / nameplate fan HP for spreadsheet rail."
            ),
            assumption_method="engineering_judgment" if ss_fan_hp is None else "nameplate",
            linked_measure_ids=linked,
        )
    )
    inputs.append(
        engineering_input(
            input_id="ep_fan_hp",
            display_name="Fan power (EnergyPlus autosized)",
            value=ep_hp,
            unit="hp",
            rail="energyplus",
            source_type="EnergyPlus_autosized" if ep_fan_hp is not None else "agent_inferred",
            assumption_note=(
                "From EnergyPlus eio / sizing inventory when available; "
                "mirrored from spreadsheet rail when EP sizing absent."
                if ep_fan_hp is None
                else "Parsed from EnergyPlus Component Sizing / eio inventory."
            ),
            assumption_method="eio_autosize" if ep_fan_hp is not None else "engineering_judgment",
            linked_measure_ids=linked,
            source_reference="eplusout.eio" if ep_fan_hp is not None else "",
        )
    )

    if ss_cooling_tons is not None or ep_cooling_tons is not None:
        ss_tons = ss_cooling_tons if ss_cooling_tons is not None else ep_cooling_tons
        ep_tons = ep_cooling_tons if ep_cooling_tons is not None else ss_cooling_tons
        inputs.append(
            engineering_input(
                input_id="ss_cooling_tons",
                display_name="Cooling capacity (spreadsheet)",
                value=ss_tons,
                unit="ton",
                rail="spreadsheet",
                source_type="nameplate" if ss_cooling_tons is not None else "engineering_assumption",
                assumption_note="Spreadsheet cooling tons for ESCO kW/ton screens.",
                assumption_method="nameplate" if ss_cooling_tons is not None else "engineering_judgment",
                linked_measure_ids=linked,
            )
        )
        inputs.append(
            engineering_input(
                input_id="ep_cooling_tons",
                display_name="Cooling capacity (EnergyPlus)",
                value=ep_tons,
                unit="ton",
                rail="energyplus",
                source_type=(
                    "EnergyPlus_autosized" if ep_cooling_tons is not None else "agent_inferred"
                ),
                assumption_note="EnergyPlus plant / coil autosized cooling capacity.",
                assumption_method="eio_autosize" if ep_cooling_tons is not None else "engineering_judgment",
                linked_measure_ids=linked,
            )
        )

    if ss_fan_hours is not None:
        inputs.append(
            engineering_input(
                input_id="ss_fan_hours",
                display_name="Fan full-load hours (spreadsheet)",
                value=ss_fan_hours,
                unit="h/yr",
                rail="spreadsheet",
                source_type="agent_inferred",
                assumption_note=(
                    "FLH for spreadsheet formulas — not Twin AMY calendar FanAvail hours "
                    "(BUG-ECM-014: never silently paste calendar over FLH)."
                ),
                assumption_method="flh_from_cascade",
                linked_measure_ids=linked,
            )
        )
    if ep_fan_hours is not None:
        inputs.append(
            engineering_input(
                input_id="ep_fan_hours",
                display_name="Fan availability hours (EnergyPlus)",
                value=ep_fan_hours,
                unit="h/yr",
                rail="energyplus",
                source_type="EnergyPlus_derived",
                assumption_note=(
                    "Calendar / schedule FanAvail hours from Twin AMY period — "
                    "distinct from spreadsheet FLH."
                ),
                assumption_method="amy_calendar_hours",
                linked_measure_ids=linked,
            )
        )
    return inputs


def _hour_bases_from_row(row: dict[str, Any]) -> dict[str, Any]:
    bases: dict[str, Any] = {}
    for key in (
        "hour_bases",
        "hours",
        "sched_hours_saved",
        "fan_hours",
        "lockout_hours",
        "sat_hours",
        "standby_hours",
        "flh",
    ):
        if key in row and row[key] is not None:
            bases[key] = row[key]
    return bases


def _measure_from_cascade_row(
    row: dict[str, Any],
    *,
    baseline_run_id: str,
    comparison_mode: str = "vs_common_baseline",
) -> dict[str, Any]:
    mid = str(row.get("measure_id") or "")
    vs = row.get("vs_baseline") or {}
    run_id = str(row.get("run_id") or row.get("out_dir") or mid or "unknown")
    return {
        "measure_id": mid,
        "run_id": run_id,
        "baseline_run_id": baseline_run_id,
        "comparison_mode": row.get("comparison_mode") or comparison_mode,
        "result_scope": row.get("result_scope") or "whole_building",
        "allocation_status": row.get("allocation_status") or "model_metered",
        "hour_bases": _hour_bases_from_row(row),
        "savings": {
            "kwh_saved": _f(vs.get("kwh_saved") if isinstance(vs, dict) else None)
            if isinstance(vs, dict)
            else _f(row.get("kwh_saved")),
            "therms_saved": _f(vs.get("therms_saved") if isinstance(vs, dict) else None)
            if isinstance(vs, dict)
            else _f(row.get("therms_saved")),
            "cost_saved_usd": _f(vs.get("cost_saved_usd") if isinstance(vs, dict) else None)
            if isinstance(vs, dict)
            else _f(row.get("cost_saved_usd")),
        },
        "patch_ok": row.get("patch_ok"),
        "error": row.get("error"),
    }


def build_ecm_simulation_evidence(
    *,
    cascade_report: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    facility: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
    package_runs: list[dict[str, Any]] | None = None,
    sequential_cascades: list[dict[str, Any]] | None = None,
    run_artifacts: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build ``ecm_simulation_evidence_v1`` document (synthetic-friendly)."""
    cascade_report = cascade_report or {}
    profile = profile or {}
    twin_run = str(
        cascade_report.get("twin_run")
        or cascade_report.get("run_id")
        or ((baseline or {}).get("run_id") if baseline else None)
        or "synthetic_baseline"
    )
    baseline_run_id = str(
        (baseline or {}).get("run_id")
        or cascade_report.get("baseline_run_id")
        or twin_run
        or "baseline"
    )

    measures: list[dict[str, Any]] = []
    for row in cascade_report.get("savings_by_measure") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("measure_id") or "")
        if not mid or mid.lower() == "baseline":
            continue
        measures.append(
            _measure_from_cascade_row(row, baseline_run_id=baseline_run_id)
        )

    equip = dict(sizing or cascade_report.get("equipment_autosizing") or {})
    if not equip and profile:
        # Soft profile hints only — stamped as screening, not measured.
        hint: dict[str, Any] = {}
        for k in ("fan_hp", "cooling_tons", "heating_mmbtu"):
            if profile.get(k) is not None:
                hint[k] = profile[k]
        if hint:
            equip = {"source": "profile_screening", **hint}

    weather_block = weather
    if weather_block is None:
        ws = cascade_report.get("weather_suitability")
        weather_block = ws if isinstance(ws, dict) else {"suitability": ws}

    model_block = model or {
        "twin_run": twin_run or None,
        "source": cascade_report.get("source") or "cascade_measures_on_twin",
    }

    doc: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "project": project
        or {
            "project_id": profile.get("project_id") or profile.get("building_id") or "unknown",
            "updated_at": _utc_now(),
        },
        "facility": facility
        or {
            "building_type": profile.get("building_type"),
            "floor_area_ft2": profile.get("floor_area_ft2")
            or profile.get("conditioned_floor_area_ft2"),
            "city": profile.get("city"),
        },
        "baseline": baseline
        or {
            "run_id": baseline_run_id,
            "twin_run": twin_run or None,
        },
        "model": model_block,
        "weather": weather_block or {},
        "equipment_autosizing": equip,
        "individual_measures": measures,
        "package_runs": list(package_runs or []),
        "sequential_cascades": list(
            sequential_cascades
            or (
                [
                    {
                        "cascade_id": cascade_report.get("run_id") or twin_run,
                        "out_dir": cascade_report.get("out_dir"),
                        "report_path": cascade_report.get("report_path"),
                        "measure_ids": [m["measure_id"] for m in measures],
                    }
                ]
                if cascade_report
                else []
            )
        ),
        "run_artifacts": list(
            run_artifacts
            or (
                [{"path": cascade_report.get("report_path"), "kind": "cascade_report"}]
                if cascade_report.get("report_path")
                else []
            )
        ),
        "warnings": list(warnings or []),
    }
    if calibration is not None:
        doc["calibration"] = calibration
    elif cascade_report.get("calibration") is not None:
        doc["calibration"] = cascade_report["calibration"]
    return doc


def write_engineering_inputs(
    path: Path | str,
    inputs: list[dict[str, Any]],
    *,
    validate: bool = True,
) -> Path:
    path = Path(path)
    if validate:
        issues = validate_engineering_inputs(inputs)
        if issues:
            raise ValueError("; ".join(issues))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema_version": INPUTS_SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "inputs": inputs,
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def export_ecm_simulation_evidence(
    out_dir: Path | str,
    *,
    cascade_report: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    facility: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
    package_runs: list[dict[str, Any]] | None = None,
    sequential_cascades: list[dict[str, Any]] | None = None,
    run_artifacts: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    write_inputs: bool = True,
    ss_fan_hp: float | None = None,
    ep_fan_hp: float | None = None,
    ss_cooling_tons: float | None = None,
    ep_cooling_tons: float | None = None,
    ss_fan_hours: float | None = None,
    ep_fan_hours: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write ``ecm_simulation_evidence.json`` (+ optional dual-rail inputs sidecar).

    Synthetic-friendly: works from cascade report + optional sizing dict alone.
    ``dry_run=True`` builds payloads without writing files.
    """
    out_dir = Path(out_dir)
    evidence = build_ecm_simulation_evidence(
        cascade_report=cascade_report,
        sizing=sizing,
        profile=profile,
        project=project,
        facility=facility,
        baseline=baseline,
        calibration=calibration,
        model=model,
        weather=weather,
        package_runs=package_runs,
        sequential_cascades=sequential_cascades,
        run_artifacts=run_artifacts,
        warnings=warnings,
    )

    equip = evidence.get("equipment_autosizing") or {}
    if ss_fan_hp is None:
        ss_fan_hp = _f(equip.get("fan_hp") or (profile or {}).get("fan_hp"))
    if ep_fan_hp is None:
        ep_fan_hp = _f(equip.get("ep_fan_hp") or equip.get("fan_hp_autosized"))
    if ss_cooling_tons is None:
        ss_cooling_tons = _f(equip.get("cooling_tons") or (profile or {}).get("cooling_tons"))
    if ep_cooling_tons is None:
        ep_cooling_tons = _f(equip.get("ep_cooling_tons") or equip.get("cooling_tons_autosized"))

    linked = [m["measure_id"] for m in evidence.get("individual_measures") or [] if m.get("measure_id")]
    inputs = build_dual_rail_sizing_inputs(
        ss_fan_hp=ss_fan_hp,
        ep_fan_hp=ep_fan_hp,
        ss_cooling_tons=ss_cooling_tons,
        ep_cooling_tons=ep_cooling_tons,
        ss_fan_hours=ss_fan_hours,
        ep_fan_hours=ep_fan_hours,
        linked_measure_ids=linked,
    )

    result: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "evidence": evidence,
        "inputs": inputs,
        "evidence_path": None,
        "inputs_path": None,
    }
    if dry_run:
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    ev_path = out_dir / EVIDENCE_FILENAME
    ev_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    result["evidence_path"] = str(ev_path)

    if write_inputs:
        in_path = write_engineering_inputs(out_dir / INPUTS_FILENAME, inputs)
        result["inputs_path"] = str(in_path)
    return result


def maybe_export_from_agent_build(
    out_dir: Path | str,
    *,
    report: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Light hook for agent-build: emit evidence when cascade/sizing available."""
    report = report or {}
    has_cascade = bool(report.get("savings_by_measure"))
    has_sizing = bool(sizing) or bool(report.get("equipment_autosizing"))
    if not has_cascade and not has_sizing and not profile:
        # Still emit a minimal dual-rail pair so Stage-1 sidecars exist for dry paths.
        return export_ecm_simulation_evidence(
            out_dir,
            cascade_report={},
            profile=profile or {},
            sizing=sizing,
            dry_run=dry_run,
            warnings=["agent_build: no cascade savings — synthetic dual-rail Inputs only"],
        )
    return export_ecm_simulation_evidence(
        out_dir,
        cascade_report=report if has_cascade or report else {},
        profile=profile,
        sizing=sizing or report.get("equipment_autosizing"),
        dry_run=dry_run,
    )


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "EVIDENCE_FILENAME",
    "INPUTS_FILENAME",
    "INPUTS_SCHEMA_VERSION",
    "engineering_input",
    "validate_engineering_inputs",
    "build_dual_rail_sizing_inputs",
    "build_ecm_simulation_evidence",
    "write_engineering_inputs",
    "export_ecm_simulation_evidence",
    "maybe_export_from_agent_build",
]
