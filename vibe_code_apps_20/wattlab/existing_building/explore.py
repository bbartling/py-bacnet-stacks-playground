"""Orchestration for the Existing Building Hypothesis Lab."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from wattlab.defaults import resolve_profile
from wattlab.existing_building.field_measurements import rank_recommended_measurements
from wattlab.existing_building.proxy_compare import compare_proxy_results
from wattlab.existing_building.report import build_existing_building_report

REQUIRED_ARTIFACTS = (
    "run_manifest.json",
    "evidence_inventory.json",
    "resolved_building_profile.json",
    "assumption_register.json",
    "autosizing_inventory.json",
    "scenario_registry.json",
    "scenario_results.csv",
    "scenario_results.json",
    "scenario_ranking.json",
    "calibration_or_hypothesis_scorecard.json",
    "proxy_crosscheck.csv",
    "proxy_crosscheck.json",
    "weather_quality_report.json",
    "energyplus_warnings_summary.json",
    "recommended_field_measurements.json",
    "wattlab_existing_building_report.html",
)

_CAPACITY_CATEGORIES = (
    "cooling_plant",
    "heating_plant",
    "supply_airflow",
    "cooling_coils",
    "heating_coils",
    "terminal_airflow",
    "fan_pressure",
    "fan_power",
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                    for key, value in row.items()
                }
            )


def _load_mapping(config: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(config, Mapping):
        return dict(config)
    import yaml

    loaded = yaml.safe_load(Path(config).read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Existing-building config must be a YAML mapping")
    return loaded


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, Mapping):
        rows: list[tuple[str, Any]] = []
        for key in sorted(value):
            rows.extend(_flatten(value[key], f"{prefix}.{key}" if prefix else str(key)))
        return rows
    return [(prefix, value)]


def _evidence_inventory(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    excluded = {"capacity", "operating_hours", "ventilation", "search", "proxy"}
    rows = [
        {
            "field": field,
            "value": value,
            "provenance": "user_reported",
            "confidence": "MEDIUM",
            "is_measured": False,
        }
        for field, value in _flatten({k: v for k, v in config.items() if k not in excluded})
        if value is not None
    ]
    seed = config.get("vibe19_dump") or config.get("vibe19_seed_fields")
    if isinstance(seed, (str, Path)) and Path(seed).is_file():
        try:
            seed = json.loads(Path(seed).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            seed = {"dump_path": str(seed)}
    if isinstance(seed, Mapping):
        rows.extend(
            {
                "field": f"vibe19.{field}",
                "value": value,
                "provenance": "vibe19_seed",
                "confidence": "MEDIUM",
                "is_measured": False,
            }
            for field, value in _flatten(seed)
            if value is not None
        )
    for row in rows:
        explicit = row["value"] if isinstance(row["value"], Mapping) else None
        if explicit and explicit.get("source") == "measured":
            row["is_measured"] = True
            row["confidence"] = explicit.get("confidence", "HIGH")
    return rows


def _hash_scenario(kind: str, parameters: Mapping[str, Any], patches: list[dict[str, Any]]) -> str:
    payload = {"scenario_type": kind, "parameters": parameters, "patches": patches}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _scenario(kind: str, name: str, parameters: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    digest = _hash_scenario(kind, parameters, patches)
    return {
        "scenario_id": f"{kind}-{digest[:12]}",
        "scenario_hash": digest,
        "scenario_type": kind,
        "name": name,
        "parameters": parameters,
        "patches": patches,
    }


def _normalize_schedule_configs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = config.get("operating_hours")
    if isinstance(raw, list) and raw:
        return [dict(item) if isinstance(item, Mapping) else {"name": str(item)} for item in raw]
    if isinstance(raw, Mapping):
        # Mission-style occupied windows + weather extensions → named strategies.
        strategies = [
            {"name": "normal_fixed", "strategy": "fan_avail_occupied_office"},
            {"name": "hot_early_late", "strategy_id": "hot_early_start"},
            {"name": "cold_early_late", "strategy_id": "cold_early_start"},
        ]
        if (raw.get("weather_extensions") or {}).get("hot", {}).get("allow_overnight"):
            strategies.append({"name": "hot_overnight", "strategy_id": "overnight_extreme"})
        if (raw.get("weather_extensions") or {}).get("cold", {}).get("allow_overnight"):
            strategies.append({"name": "cold_overnight", "strategy_id": "overnight_extreme"})
        return strategies
    return [
        {"name": "continuous", "strategy": "fan_avail_continuous"},
        {"name": "occupied_office", "strategy": "fan_avail_occupied_office"},
    ]


def _normalize_ventilation_configs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if config.get("ventilation"):
        return [dict(item) for item in config["ventilation"]]
    names = config.get("ventilation_scenarios") or []
    if not names:
        return [
            {"name": "zero_oa", "oa_fraction": 0.0},
            {"name": "half_oa", "oa_fraction": 0.5},
            {"name": "design_oa", "oa_fraction": 1.0},
        ]
    out: list[dict[str, Any]] = []
    for name in names:
        key = str(name)
        if key in {"stuck_closed", "0.0", "zero"}:
            out.append({"name": key, "oa_fraction": 0.0, "stuck_closed": key == "stuck_closed"})
        elif key in {"archetype", "design", "1.0"}:
            out.append({"name": key, "oa_fraction": 1.0})
        else:
            try:
                out.append({"name": f"oa_{key}", "oa_fraction": float(key)})
            except ValueError:
                out.append({"name": key, "oa_fraction": 1.0})
    return out


def _normalize_capacity_configs(config: Mapping[str, Any]) -> tuple[list[float], list[dict[str, float]]]:
    capacity_cfg = config.get("capacity") or {}
    factors = list(capacity_cfg.get("factors") or [])
    independent = [dict(item) for item in (capacity_cfg.get("independent_factors") or [])]
    # Mission-style: capacity_factors: {cooling_plant: [1.0, 0.7], ...}
    by_type = config.get("capacity_factors") or {}
    if isinstance(by_type, Mapping) and by_type:
        grid_vals = sorted(
            {
                float(v)
                for values in by_type.values()
                if isinstance(values, (list, tuple))
                for v in values
            }
        )
        if not factors:
            factors = grid_vals or [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
        # One independent case using the lowest listed factor per category.
        independent.append(
            {
                str(key): float(min(values))
                for key, values in by_type.items()
                if isinstance(values, (list, tuple)) and values
            }
        )
    if not factors:
        factors = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    return factors, independent


def _build_scenarios(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    baseline = _scenario("reference", "Autosized reference", {}, [])
    factors, independent_factors = _normalize_capacity_configs(config)
    capacity = []
    for factor in factors:
        uniform = {category: float(factor) for category in _CAPACITY_CATEGORIES}
        capacity.append(
            _scenario(
                "capacity",
                f"Uniform capacity {float(factor):.0%}",
                {"factor": float(factor), "factors": uniform},
                [{"name": "capacity_factors", "params": {"factors": uniform}}],
            )
        )
    for factors_by_type in independent_factors:
        if not factors_by_type:
            continue
        normalized = {str(key): float(value) for key, value in sorted(factors_by_type.items())}
        capacity.append(
            _scenario(
                "capacity",
                "Independent capacity factors",
                {"factor": min(normalized.values()), "factors": normalized},
                [{"name": "capacity_factors", "params": {"factors": normalized}}],
            )
        )
    schedules = []
    for item in _normalize_schedule_configs(config):
        strategy = item.get("strategy")
        patches = [{"name": strategy, "params": {}}] if strategy in {
            "fan_avail_continuous", "fan_avail_occupied_office"
        } else []
        item["implementation"] = "schedule_patch" if patches else "planned_schedule_stub"
        schedules.append(
            _scenario(
                "operating_hours",
                str(item.get("name", strategy or item.get("strategy_id") or "schedule")),
                item,
                patches,
            )
        )
    ventilation = []
    for item in _normalize_ventilation_configs(config):
        fraction = float(item.get("oa_fraction", item.get("min_oa_fraction", 1.0)))
        params = {"min_oa_fraction": fraction, "stuck_closed": bool(item.get("stuck_closed", False))}
        ventilation.append(
            _scenario(
                "ventilation",
                str(item.get("name", f"OA {fraction:.0%}")),
                {**item, "oa_fraction": fraction},
                [{"name": "outdoor_air_fraction", "params": params}],
            )
        )
    ofat = [baseline, *capacity, *schedules, *ventilation]
    search_cfg = config.get("search") or {}
    raw_max = search_cfg.get("max_scenarios", config.get("max_scenarios", 50))
    max_scenarios = max(1, int(raw_max))
    combined = []
    for cap, schedule, vent in itertools.product(capacity, schedules, ventilation):
        parameters = {
            "capacity": cap["parameters"],
            "operating_hours": schedule["parameters"],
            "ventilation": vent["parameters"],
        }
        combined.append(
            _scenario(
                "combined",
                f"{cap['name']} + {schedule['name']} + {vent['name']}",
                parameters,
                [*cap["patches"], *schedule["patches"], *vent["patches"]],
            )
        )
        if len(ofat) + len(combined) >= max_scenarios:
            break
    return (ofat + combined)[:max_scenarios]


def _has_bills(config: Mapping[str, Any]) -> bool:
    if config.get("monthly_bills"):
        return True
    path = config.get("monthly_bills_path")
    return bool(path and Path(path).is_file())


def _proxy_inputs(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for spec in (config.get("proxy") or {}).get("calculators") or []:
        try:
            from wattlab.bench import esco as _esco  # noqa: F401
            from wattlab.bench.registry import get

            result = get(str(spec["name"]))(dict(spec.get("inputs") or {}))
            if spec.get("scenario_id"):
                outputs[str(spec["scenario_id"])] = result
        except (KeyError, TypeError, ValueError) as exc:
            if spec.get("scenario_id"):
                outputs[str(spec["scenario_id"])] = {"applicable": False, "note": str(exc)}
    return outputs


def run_explore_existing(
    config: Mapping[str, Any] | str | Path,
    *,
    dry_run: bool = True,
    live: bool = False,
    out_dir: str | Path = "wattlab_existing_building_output",
) -> dict[str, Any]:
    """Run a bounded, provenance-aware existing-building hypothesis search."""
    if dry_run and live:
        raise ValueError("Choose either dry_run or live, not both")
    cfg = _load_mapping(config)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence = _evidence_inventory(cfg)
    profile = resolve_profile(cfg.get("profile") or cfg)
    assumptions = [
        {
            "parameter": name,
            "value": detail.get("value"),
            "source": detail.get("source"),
            "confidence": "LOW" if detail.get("source") == "default" else "MEDIUM",
        }
        for name, detail in sorted((profile.get("field_sources") or {}).items())
        if detail.get("source") != "user"
    ]
    scenarios = _build_scenarios(cfg)
    # VALIDATED requires an explicit held-out period that has already been judged
    # passing; presence of bills alone never awards VALIDATED.
    if _has_bills(cfg) and bool(cfg.get("holdout_period")) and bool(cfg.get("holdout_passed")):
        badge = "VALIDATED"
    elif _has_bills(cfg):
        badge = "MONTHLY_CALIBRATED"
    else:
        badge = "CONCEPTUAL_HYPOTHESIS"

    sizing: dict[str, Any] = {
        "status": "PLANNED" if not live else "PENDING",
        "steps": ["resolve profile", "run autosized reference", "parse sizing inventory"],
    }
    live_runs: dict[str, dict[str, Any]] = {}
    if live:
        from wattlab.energyplus.runner import run_scenario
        from wattlab.energyplus.sizing import freeze_autosized_values, parse_sizing_inventory

        idf = Path(profile["energyplus"]["prototype_idf"])
        epw = Path(profile["energyplus"]["epw"])
        reference = scenarios[0]
        reference_run = run_scenario(
            idf,
            epw,
            out / "runs" / reference["scenario_id"],
            patches=reference["patches"],
            dry_run=False,
            cache_dir=out / ".cache",
        )
        live_runs[reference["scenario_id"]] = reference_run
        sizing = parse_sizing_inventory(Path(reference_run["output_dir"]))
        frozen_idf = out / "autosized_reference_frozen.idf"
        sizing["freeze_metadata"] = freeze_autosized_values(idf, frozen_idf, sizing)
        sizing["status"] = "PARSED_AND_FROZEN"
        scenario_idf = frozen_idf if sizing["freeze_metadata"].get("ok") else idf
        for scenario in scenarios[1:]:
            run = run_scenario(
                scenario_idf,
                epw,
                out / "runs" / scenario["scenario_id"],
                patches=scenario["patches"],
                dry_run=False,
                cache_dir=out / ".cache",
            )
            live_runs[scenario["scenario_id"]] = run

    baseline_kwh = None
    if live_runs:
        baseline_kwh = live_runs[scenarios[0]["scenario_id"]].get("annual", {}).get("electricity_kwh_year")
    results: list[dict[str, Any]] = []
    warnings = []
    for scenario in scenarios:
        run = live_runs.get(scenario["scenario_id"], {})
        annual_kwh = run.get("annual", {}).get("electricity_kwh_year")
        savings = (
            float(baseline_kwh) - float(annual_kwh)
            if baseline_kwh is not None and annual_kwh is not None
            else None
        )
        row = {
            **scenario,
            "status": run.get("status", "PLANNED"),
            "annual_electricity_kwh": annual_kwh,
            "savings_kwh": savings,
            "savings_claim": "SIMULATED_DIFFERENCE" if savings is not None else "NOT_EVALUATED",
            "unmet_hours": run.get("annual", {}).get("unmet_hours"),
            "runtime_hours": run.get("annual", {}).get("runtime_hours"),
        }
        results.append(row)
        if run.get("err"):
            warnings.append({"scenario_id": scenario["scenario_id"], **run["err"]})

    ranking = [
        {
            "rank": rank,
            "scenario_id": row["scenario_id"],
            "scenario_type": row["scenario_type"],
            "score": row["savings_kwh"],
            "basis": "simulated_energy_difference" if row["savings_kwh"] is not None else "insufficient_evidence",
        }
        for rank, row in enumerate(
            sorted(results, key=lambda item: (item["savings_kwh"] is None, -(item["savings_kwh"] or 0), item["scenario_id"])),
            1,
        )
    ]
    proxies = compare_proxy_results(results, _proxy_inputs(cfg))
    sensitivities = {
        f"{row['scenario_type']}.{row['scenario_id']}": abs(float(row["savings_kwh"] or 0))
        for row in results
    }
    uncertain = [
        {"parameter": "operating_hours.schedule", "uncertainty": 0.9, "sensitivity": 0.8},
        {"parameter": "ventilation.outdoor_air", "uncertainty": 0.9, "sensitivity": 0.9},
        {"parameter": "capacity.installed", "uncertainty": 0.7, "sensitivity": 0.7},
        *[{"parameter": item["parameter"], "uncertainty": 0.6, "sensitivity": 0.5} for item in assumptions],
    ]
    measurements = rank_recommended_measurements(uncertain, sensitivities)
    scorecard = {
        "badge": badge,
        "has_monthly_bills": _has_bills(cfg),
        "has_holdout_period": bool(cfg.get("holdout_period")),
        "validated": badge == "VALIDATED",
        "note": (
            "VALIDATED is only assigned when monthly bills exist, a holdout "
            "period is configured, and holdout_passed is true."
        ),
    }
    weather = {
        "epw": profile["energyplus"].get("epw"),
        "quality": "NOT_ASSESSED" if dry_run else "INPUT_PRESENT",
        "extensions": cfg.get("weather_extensions") or [],
        "limitations": ["No measured-site weather quality is inferred from a filename."],
    }
    manifest = {
        "workflow": "existing_building_hypothesis_lab",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "badge": badge,
        "scenario_count": len(scenarios),
        "max_scenarios": int((cfg.get("search") or {}).get("max_scenarios", 50)),
        "artifacts": list(REQUIRED_ARTIFACTS),
    }
    artifacts = {
        "run_manifest.json": manifest,
        "evidence_inventory.json": evidence,
        "resolved_building_profile.json": profile,
        "assumption_register.json": assumptions,
        "autosizing_inventory.json": sizing,
        "scenario_registry.json": scenarios,
        "scenario_results.json": results,
        "scenario_ranking.json": ranking,
        "calibration_or_hypothesis_scorecard.json": scorecard,
        "proxy_crosscheck.json": proxies,
        "weather_quality_report.json": weather,
        "energyplus_warnings_summary.json": {"scenario_warnings": warnings, "count": len(warnings)},
        "recommended_field_measurements.json": measurements,
    }
    for name, value in artifacts.items():
        _write_json(out / name, value)
    _write_csv(out / "scenario_results.csv", results)
    _write_csv(out / "proxy_crosscheck.csv", proxies)
    build_existing_building_report(
        out / "wattlab_existing_building_report.html",
        badge=badge,
        profile=profile,
        evidence=evidence,
        assumptions=assumptions,
        scenarios=scenarios,
        ranking=ranking,
        proxy_crosscheck=proxies,
        measurements=measurements,
        limitations=[
            "Sparse inputs create hypotheses, not measured facts.",
            "Reduced capacity is not an energy-saving claim; unmet load and runtime must be reviewed.",
            "Dry-run values are plans and contain no simulated performance.",
        ],
    )
    return {"out_dir": str(out), "badge": badge, "scenarios": len(scenarios), "artifacts": list(REQUIRED_ARTIFACTS)}
