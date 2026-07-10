"""Importable Agent API for AFDD / RCx — no HTTP server, Streamlit-free.

Agents load packages/folders, run the 50-rule cookbook, analytics, and RCx
coverage, then export a machine-readable bundle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.analytics import (
    dataset_time_span,
    mech_cooling_oat_bins,
    motor_run_hours_table,
    motor_run_hours_weekly,
)
from app.column_map_json import (
    merge_column_map_into_role_map,
    to_haystack_document,
)
from app.data_loader import load_building_folder as _load_building_folder_frames
from app.data_loader import load_equipment_csv
from app.package_io import (
    SESSION_SCHEMA,
    load_package_from_dir,
    load_package_zip,
    resolve_building_root,
)
from app.reports import results_summary_table
from app.role_map_gap import build_role_map_gap_report
from app.rules.base import RuleResult
from app.rules.runner import RULES, run_batch
from app.site_model import equipment_type_from_id
from app.tuning_report import build_tuning_assistant_report
from app.weather_psychrometrics import enrich_weather_frame
from app.weather_resolver import has_web_oat


@dataclass
class AgentDataset:
    """Loaded building data ready for rules / analytics / RCx."""

    building_id: str
    frames: dict[str, pd.DataFrame]
    weather: pd.DataFrame | None
    role_map: dict[str, dict[str, str]] = field(default_factory=dict)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    unit_system: str = "imperial"
    prefer_web_oat: bool = True
    column_map: dict[str, Any] | None = None
    package_report: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_path: str = ""
    workdir: Path | None = None
    session_config: dict[str, Any] | None = None

    @property
    def has_web_weather(self) -> bool:
        return has_web_oat(self.weather)


@dataclass
class AgentRun:
    """Results from ``run_rules`` (and optional analytics / RCx attachments)."""

    results: list[RuleResult] = field(default_factory=list)
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    status_counts: dict[str, int] = field(default_factory=dict)
    top_faults: pd.DataFrame = field(default_factory=pd.DataFrame)
    analytics: dict[str, pd.DataFrame] = field(default_factory=dict)
    rcx_coverage: pd.DataFrame = field(default_factory=pd.DataFrame)
    gap_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    tuning_report: dict[str, Any] = field(default_factory=dict)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def make_session_config(
    role_map: dict[str, dict[str, str]] | None = None,
    params: dict[str, dict[str, Any]] | None = None,
    *,
    unit_system: str = "imperial",
    prefer_web_oat: bool = True,
    chw_leave_max_f: float | None = None,
    include_ahu_chw_valve: bool | None = None,
) -> dict[str, Any]:
    """Build an ``openfdd_session_v1`` dict suitable for JSON export."""
    out: dict[str, Any] = {
        "schema_version": SESSION_SCHEMA,
        "unit_system": unit_system,
        "prefer_web_oat": bool(prefer_web_oat),
        "role_map": role_map or {},
        "params": params or {},
    }
    if chw_leave_max_f is not None:
        out["chw_leave_max_f"] = float(chw_leave_max_f)
    if include_ahu_chw_valve is not None:
        out["include_ahu_chw_valve"] = bool(include_ahu_chw_valve)
    return out


def _attach_role_map(frames: dict[str, pd.DataFrame], role_map: dict[str, dict[str, str]]) -> None:
    for eq_id, df in frames.items():
        df.attrs["_role_map"] = role_map
        df.attrs.setdefault("equipment_id", eq_id)
        df.attrs.setdefault("equipment_type", equipment_type_from_id(eq_id))


def _load_weather_near(building_root: Path) -> pd.DataFrame | None:
    candidates = [
        building_root / "weather" / "history_wide.csv",
        building_root.parent / "weather" / "history_wide.csv",
    ]
    for hist in candidates:
        if not hist.is_file():
            continue
        cols = hist.parent / "columns.csv"
        try:
            df = load_equipment_csv(hist, cols if cols.is_file() else None)
            return enrich_weather_frame(df)
        except Exception:
            continue
    return None


def _dataset_from_package(result, *, source_path: str) -> AgentDataset:
    role_map: dict[str, dict[str, str]] = {}
    params: dict[str, dict[str, Any]] = {}
    unit_system = "imperial"
    prefer_web = True
    session_dict: dict[str, Any] | None = None

    if result.session_config is not None:
        cfg = result.session_config
        session_dict = cfg.model_dump()
        if cfg.role_map:
            role_map = {str(k): dict(v) for k, v in cfg.role_map.items() if isinstance(v, dict)}
        if cfg.params:
            params = {str(k): dict(v) for k, v in cfg.params.items() if isinstance(v, dict)}
        if cfg.unit_system:
            unit_system = cfg.unit_system
        if cfg.prefer_web_oat is not None:
            prefer_web = bool(cfg.prefer_web_oat)

    if result.column_map:
        role_map = merge_column_map_into_role_map(role_map, result.column_map, prefer_json=True)

    frames = result.frames
    for eq_id, df in frames.items():
        df.attrs.setdefault("building_id", result.manifest.building_id)
        df.attrs.setdefault("equipment_type", equipment_type_from_id(eq_id))
    _attach_role_map(frames, role_map)

    return AgentDataset(
        building_id=result.manifest.building_id,
        frames=frames,
        weather=result.weather,
        role_map=role_map,
        params=params,
        unit_system=unit_system,
        prefer_web_oat=prefer_web,
        column_map=result.column_map,
        package_report=dict(result.report),
        warnings=list(result.warnings),
        source_path=source_path,
        workdir=Path(result.workdir) if result.workdir else None,
        session_config=session_dict,
    )


def load_package_path(path: str | Path) -> AgentDataset:
    """Load an ``openfdd_package_v1`` zip or an already-extracted package directory."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Package path not found: {p}")
    if p.is_file() and p.suffix.lower() == ".zip":
        result = load_package_zip(p.read_bytes())
        return _dataset_from_package(result, source_path=str(p))
    if p.is_dir():
        # Extracted package (has manifest) or workdir containing one child
        try:
            root = resolve_building_root(p) if not (p / "manifest.json").is_file() else p
        except Exception:
            root = p
        if (root / "manifest.json").is_file():
            result = load_package_from_dir(root, workdir=p)
            return _dataset_from_package(result, source_path=str(p))
        # Fall through to folder loader
        return load_building_folder(p)
    raise ValueError(f"Unsupported package path: {p}")


def load_building_folder(path: str | Path) -> AgentDataset:
    """Load a historian building folder (equipment subdirs + optional weather)."""
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"Building folder not found: {p}")
    # Prefer package loader when manifest present
    if (p / "manifest.json").is_file():
        result = load_package_from_dir(p, workdir=p)
        return _dataset_from_package(result, source_path=str(p))

    frames = _load_building_folder_frames(p)
    if not frames:
        raise ValueError(f"No equipment frames under {p}")
    weather = _load_weather_near(p)
    role_map: dict[str, dict[str, str]] = {}
    params: dict[str, dict[str, Any]] = {}
    session_dict = None
    sc_path = p / "session_config.json"
    if sc_path.is_file():
        try:
            from app.package_io import SessionConfig

            raw = json.loads(sc_path.read_text(encoding="utf-8"))
            cfg = SessionConfig.model_validate(raw)
            session_dict = cfg.model_dump()
            if cfg.role_map:
                role_map = {str(k): dict(v) for k, v in cfg.role_map.items() if isinstance(v, dict)}
            if cfg.params:
                params = {str(k): dict(v) for k, v in cfg.params.items() if isinstance(v, dict)}
        except Exception:
            pass
    cm_path = p / "column_map.json"
    column_map = None
    warnings: list[str] = []
    if cm_path.is_file():
        from app.column_map_json import load_column_map_json, validate_column_map_against_frames

        column_map = load_column_map_json(cm_path)
        role_map = merge_column_map_into_role_map(role_map, column_map, prefer_json=True)
        warnings.extend(validate_column_map_against_frames(column_map, frames)[:20])

    for eq_id, df in frames.items():
        df.attrs.setdefault("building_id", p.name)
        df.attrs.setdefault("equipment_type", equipment_type_from_id(eq_id))
    _attach_role_map(frames, role_map)
    span = dataset_time_span(frames)
    report = {
        "building_id": p.name,
        "equipment_count": len(frames),
        "equipment_ids": sorted(frames),
        "has_weather": weather is not None,
        "has_session_config": session_dict is not None,
        "has_column_map": column_map is not None,
        "start": str(span["start"]) if span.get("start") is not None else None,
        "end": str(span["end"]) if span.get("end") is not None else None,
    }
    return AgentDataset(
        building_id=p.name,
        frames=frames,
        weather=weather,
        role_map=role_map,
        params=params,
        column_map=column_map,
        package_report=report,
        warnings=warnings,
        source_path=str(p),
        session_config=session_dict,
    )


def run_rules(
    dataset: AgentDataset,
    params: dict[str, dict[str, Any]] | None = None,
    equipment_ids: list[str] | set[str] | None = None,
    rule_ids: list[str] | set[str] | None = None,
    *,
    require_operational_gates: bool = True,
) -> AgentRun:
    """Run all 50 canonical rules (optionally filtered) — never silently omit."""
    merged_params = {**dataset.params, **(params or {})}
    _attach_role_map(dataset.frames, dataset.role_map)
    eq_filter = set(equipment_ids) if equipment_ids is not None else None
    if require_operational_gates:
        results = run_batch(
            dataset.frames,
            params_by_rule=merged_params,
            weather=dataset.weather,
            equipment_filter=eq_filter,
        )
    else:
        from app.role_map import apply_role_map
        from app.rules.runner import run_all_cookbook_rules

        results = []
        for eq_id, raw_df in sorted(dataset.frames.items()):
            if eq_filter is not None and eq_id not in eq_filter:
                continue
            mapped = apply_role_map(raw_df, eq_id, dataset.role_map)
            mapped.attrs.update(raw_df.attrs)
            poll = float(raw_df.attrs.get("poll_seconds") or 300.0)
            results.extend(
                run_all_cookbook_rules(
                    mapped,
                    equipment_id=eq_id,
                    poll_seconds=poll,
                    params_by_rule=merged_params,
                    weather=dataset.weather,
                    site_id=str(raw_df.attrs.get("site_id", "")),
                    building_id=str(raw_df.attrs.get("building_id", dataset.building_id)),
                    equipment_type=str(
                        raw_df.attrs.get("equipment_type", equipment_type_from_id(eq_id))
                    ),
                    require_operational_gates=False,
                )
            )
    if rule_ids is not None:
        allow = set(rule_ids)
        results = [r for r in results if r.rule_id in allow]
    # Ensure every requested rule id still appears conceptually — when filtering,
    # callers asked for a subset; full catalog length is len(RULES)*equip when unfiltered.
    summary = results_summary_table(results)
    counts = (
        {str(k): int(v) for k, v in summary["status"].value_counts().to_dict().items()}
        if not summary.empty
        else {}
    )
    top = pd.DataFrame()
    if not summary.empty:
        faults = summary[summary["status"] == "FAULT"].copy()
        if not faults.empty and "fault_hours" in faults.columns:
            top = faults.sort_values("fault_hours", ascending=False).head(25)
    return AgentRun(
        results=results,
        summary=summary,
        status_counts=counts,
        top_faults=top,
        params=merged_params,
        meta={
            "building_id": dataset.building_id,
            "equipment_count": len(dataset.frames),
            "rule_catalog_count": len(RULES),
            "result_count": len(results),
            "has_web_weather": dataset.has_web_weather,
            "prefer_web_oat": dataset.prefer_web_oat,
            "require_operational_gates": require_operational_gates,
        },
    )


def run_analytics(
    dataset: AgentDataset,
    params: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    """Motor hours, weekly motors, mech-cooling OAT bins (web OAT primary)."""
    p = params or {}
    prefer_web = bool(p.get("prefer_web_oat", dataset.prefer_web_oat))
    motor = motor_run_hours_table(dataset.frames, dataset.role_map)
    weekly = motor_run_hours_weekly(
        dataset.frames,
        dataset.role_map,
        chw_leave_max_f=float(p.get("chw_leave_max_f", 48.0)),
        weather=dataset.weather,
        prefer_web_oat=prefer_web,
    )
    cool = mech_cooling_oat_bins(
        dataset.frames,
        dataset.role_map,
        weather=dataset.weather,
        prefer_web_oat=prefer_web,
        chw_leave_max_f=float(p.get("chw_leave_max_f", 48.0)),
        include_ahu_chw_valve=False,
    )
    return {
        "motor_hours": motor,
        "motor_weekly": weekly,
        "mech_cooling_oat_bins": cool,
    }


def run_rcx_coverage(dataset: AgentDataset) -> pd.DataFrame:
    """RCx preset coverage diagnostics."""
    from app.rcx_plots import rcx_preset_coverage

    return rcx_preset_coverage(dataset.frames, dataset.role_map, weather=dataset.weather)


def export_agent_bundle(
    dataset: AgentDataset,
    run: AgentRun | None,
    out_dir: str | Path,
    *,
    include_gap_report: bool = True,
    include_tuning_report: bool = True,
    baseline_run: AgentRun | None = None,
) -> dict[str, Path]:
    """Write run_report + CSVs + fault/session/role/column maps under ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    run = run or AgentRun(params=dataset.params)
    analytics = run.analytics or {}
    if not analytics:
        analytics = run_analytics(dataset)
        run.analytics = analytics
    rcx = run.rcx_coverage
    if rcx is None or (isinstance(rcx, pd.DataFrame) and rcx.empty):
        rcx = run_rcx_coverage(dataset)
        run.rcx_coverage = rcx

    gap = run.gap_report
    if include_gap_report and (gap is None or (isinstance(gap, pd.DataFrame) and gap.empty)):
        gap = build_role_map_gap_report(dataset.frames, dataset.role_map, weather=dataset.weather)
        run.gap_report = gap

    if include_tuning_report and not run.tuning_report:
        run.tuning_report = build_tuning_assistant_report(
            baseline=baseline_run.results if baseline_run else None,
            tuned=run.results,
            params=run.params or dataset.params,
            has_web_weather=dataset.has_web_weather,
            gap_report=gap if isinstance(gap, pd.DataFrame) else None,
        )

    report = {
        "building_id": dataset.building_id,
        "source_path": dataset.source_path,
        "package_report": dataset.package_report,
        "warnings": dataset.warnings,
        "status_counts": run.status_counts,
        "meta": run.meta,
        "tuning_report": run.tuning_report,
        "rule_catalog_count": len(RULES),
    }
    rp = out / "run_report.json"
    rp.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    written["run_report"] = rp

    if run.summary is not None and not run.summary.empty:
        p = out / "fdd_summary.csv"
        run.summary.to_csv(p, index=False)
        written["fdd_summary"] = p

    fault_settings = run.params or dataset.params or {}
    fs = out / "fault_settings.json"
    fs.write_text(json.dumps(fault_settings, indent=2), encoding="utf-8")
    written["fault_settings"] = fs

    session = make_session_config(
        dataset.role_map,
        fault_settings,
        unit_system=dataset.unit_system,
        prefer_web_oat=dataset.prefer_web_oat,
    )
    sc = out / "session_config.json"
    sc.write_text(json.dumps(session, indent=2), encoding="utf-8")
    written["session_config"] = sc

    rm = out / "role_map.yaml"
    rm.write_text(yaml.safe_dump(dataset.role_map, sort_keys=True), encoding="utf-8")
    written["role_map"] = rm

    if dataset.column_map:
        cm = out / "column_map.json"
        cm.write_text(
            json.dumps(to_haystack_document(dataset.column_map), indent=2),
            encoding="utf-8",
        )
        written["column_map"] = cm

    for key, filename in (
        ("motor_hours", "motor_hours.csv"),
        ("motor_weekly", "motor_weekly.csv"),
        ("mech_cooling_oat_bins", "mech_cooling_oat_bins.csv"),
    ):
        df = analytics.get(key)
        if df is not None and isinstance(df, pd.DataFrame):
            path = out / filename
            df.to_csv(path, index=False)
            written[key] = path

    if isinstance(rcx, pd.DataFrame):
        path = out / "rcx_preset_coverage.csv"
        rcx.to_csv(path, index=False)
        written["rcx_preset_coverage"] = path

    if include_gap_report and isinstance(gap, pd.DataFrame) and not gap.empty:
        path = out / "role_map_gap_report.csv"
        gap.to_csv(path, index=False)
        written["role_map_gap_report"] = path

    if run.tuning_report:
        path = out / "tuning_assistant_report.json"
        path.write_text(json.dumps(run.tuning_report, indent=2, default=str), encoding="utf-8")
        written["tuning_assistant_report"] = path

    # Streamlit bridge: write bootstrap so the next app start auto-loads this run
    try:
        from app.bootstrap import build_bootstrap_payload, write_bootstrap

        pkg = dataset.source_path if str(dataset.source_path).lower().endswith(".zip") else None
        folder = None if pkg else (dataset.source_path or None)
        # Prefer original zip if source_path is an extract dir but package was zip — use source_path as-is
        src = Path(dataset.source_path) if dataset.source_path else None
        if src and src.is_file() and src.suffix.lower() == ".zip":
            pkg, folder = str(src), None
        elif src and src.is_dir():
            pkg, folder = None, str(src)

        boot = build_bootstrap_payload(
            package_path=pkg,
            building_folder=folder,
            session_config=session,
            fault_settings_path=fs,
            column_map_path=written.get("column_map"),
            out_dir=out,
            auto_run_rules=True,
            notes=f"building_id={dataset.building_id}",
        )
        for bp in write_bootstrap(boot, path=out / "streamlit_bootstrap.json", also_default=True):
            written[f"bootstrap:{bp.name}"] = bp
    except Exception:
        pass  # bootstrap is best-effort; never fail the export

    return written
