"""WattLab dump helpers — sensor stats, diurnal profiles, FDD findings for vibe20.

These build the "big dump" pieces of the agent bundle: per-equipment summary
statistics of every mapped role sliced by operating state (all / fan-or-pump
on / off), 24h diurnal profiles (weekday/weekend/holiday × fan state),
occupied/unoccupied medians of every setpoint (``*-sp``) role, long-format
FDD findings, and a machine-readable MANIFEST.json.
Everything is data-model driven — only roles present in the role map are used.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

import pandas as pd

from app.column_map_json import POINT_DISPLAY, canonicalize_point
from app.daytypes import DAY_TYPES, day_type_series
from app.occupancy import OccupancySchedule, occupied_mask
from app.rcx_plots import hydronic_operating_mask, operating_mask
from app.reports import debug_frame
from app.role_map import apply_role_map
from app.rules.base import RuleResult
from app.site_model import resolve_equipment_type

# role_map meta keys that are not timeseries roles
_META_KEYS = {"chw_pump_equipment", "notes", "equipment_type", "plant_group", "cooling_technology"}

ExportProfile = Literal["summary", "diagnostic", "forensic"]

EXPORT_PROFILES: tuple[ExportProfile, ...] = ("summary", "diagnostic", "forensic")

# Never emit per-rule timeseries for these statuses (all profiles).
NEVER_TIMESERIES_STATUSES: frozenset[str] = frozenset(
    {
        "NOT_APPLICABLE_EQUIPMENT_TYPE",
        "SKIPPED_MISSING_ROLES",
        "SKIPPED_EQUIPMENT_OFF",
    }
)

# Explicit allowlists — statuses that may emit fdd_timeseries under each profile.
PROFILE_TIMESERIES_ALLOWLIST: Mapping[ExportProfile, frozenset[str]] = {
    "summary": frozenset(),
    "diagnostic": frozenset({"FAULT", "ERROR"}),
    "forensic": frozenset({"FAULT", "PASS", "ERROR"}),
}


@dataclass(frozen=True)
class ExportCounts:
    """Counts from profile-aware FDD evidence serialization."""

    written: tuple[Path, ...] = ()
    suppressed_status: Mapping[str, int] = field(default_factory=dict)
    written_status: Mapping[str, int] = field(default_factory=dict)


def _mapped_roles(role_map: dict, eq_id: str) -> list[str]:
    eq_map = role_map.get(eq_id, {}) if isinstance(role_map, dict) else {}
    return [r for r, col in eq_map.items() if r not in _META_KEYS and col and isinstance(col, str)]


def _role_series_for_frame(
    mapped: pd.DataFrame,
    roles: list[str],
) -> dict[str, tuple[pd.Series, str]]:
    """role → (series, source). Explicit role-map columns win; raw columns whose
    canonical name is a known role fill the gaps (source="column_alias")."""
    out: dict[str, tuple[pd.Series, str]] = {}
    for role in roles:
        if role in mapped.columns and mapped[role].notna().any():
            out[role] = (mapped[role], "role_map")
    for col in mapped.columns:
        canon = canonicalize_point(str(col))
        if canon in out or canon not in POINT_DISPLAY:
            continue
        if mapped[col].notna().any():
            out[canon] = (mapped[col], "column_alias")
    return out


def _stats_row(
    eq_id: str, et: str, role: str, s: pd.Series, proof: str, source: str = "role_map"
) -> dict[str, Any] | None:
    num = pd.to_numeric(s, errors="coerce").dropna()
    if num.empty:
        return None
    return {
        "equipment_id": eq_id,
        "equipment_type": et,
        "role": role,
        "source": source,
        "proof": proof,
        "n": int(len(num)),
        "mean": round(float(num.mean()), 3),
        "std": round(float(num.std(ddof=0)), 3) if len(num) > 1 else 0.0,
        "min": round(float(num.min()), 3),
        "p25": round(float(num.quantile(0.25)), 3),
        "p50": round(float(num.quantile(0.5)), 3),
        "p75": round(float(num.quantile(0.75)), 3),
        "max": round(float(num.max()), 3),
    }


def sensor_stats_tables(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
) -> dict[str, pd.DataFrame]:
    """Summary stats for every mapped role, sliced by operating state.

    Returns ``{"all": df, "fan_on": df, "fan_off": df}``. The on/off slices use
    fan proof (fan-status → fan-cmd → VAV airflow) and fall back to hydronic
    pump proof for plant equipment; equipment without any proof appears only in
    the ``all`` table (its ``proof`` column says ``none``).
    """
    rows_all: list[dict[str, Any]] = []
    rows_on: list[dict[str, Any]] = []
    rows_off: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        roles = _mapped_roles(role_map, eq_id)
        et = resolve_equipment_type(eq_id, df=raw, role_map=role_map)
        mapped = apply_role_map(raw, eq_id, role_map)
        role_series = _role_series_for_frame(mapped, roles)
        if not role_series:
            continue
        # Operating proof on a frame that also carries alias-resolved canonical
        # columns (so raw `fan_status` still proves the fan).
        aug = mapped.copy()
        for role, (s, _src) in role_series.items():
            if role not in aug.columns:
                aug[role] = s
        mask, proof = operating_mask(aug)
        if mask is None:
            mask, proof = hydronic_operating_mask(aug)
        proof_label = proof or "none"
        for role, (s, src) in role_series.items():
            row = _stats_row(eq_id, et, role, s, proof_label, src)
            if row is not None:
                rows_all.append(row)
            if mask is None:
                continue
            on = mask.reindex(s.index).fillna(False)
            row_on = _stats_row(eq_id, et, role, s.where(on), proof_label, src)
            if row_on is not None:
                rows_on.append(row_on)
            row_off = _stats_row(eq_id, et, role, s.where(~on), proof_label, src)
            if row_off is not None:
                rows_off.append(row_off)
    return {
        "all": pd.DataFrame(rows_all),
        "fan_on": pd.DataFrame(rows_on),
        "fan_off": pd.DataFrame(rows_off),
    }


def setpoints_table(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    schedule: OccupancySchedule | dict | None = None,
) -> pd.DataFrame:
    """Occupied / unoccupied medians for every mapped ``*-sp`` role.

    Occupancy uses the provided schedule (Overview schedule dict or
    :class:`OccupancySchedule`), defaulting to the standard weekday schedule.
    """
    sched = schedule if isinstance(schedule, OccupancySchedule) else OccupancySchedule.from_dict(schedule)
    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = resolve_equipment_type(eq_id, df=raw, role_map=role_map)
        mapped = apply_role_map(raw, eq_id, role_map)
        if not isinstance(mapped.index, pd.DatetimeIndex):
            continue
        role_series = _role_series_for_frame(mapped, _mapped_roles(role_map, eq_id))
        sp_roles = [r for r in role_series if r.endswith("-sp")]
        if not sp_roles:
            continue
        occ = occupied_mask(mapped.index, sched)
        for role in sp_roles:
            num = pd.to_numeric(role_series[role][0], errors="coerce")
            if num.notna().sum() == 0:
                continue
            occ_vals = num[occ.to_numpy()].dropna()
            unocc_vals = num[(~occ).to_numpy()].dropna()
            rows.append(
                {
                    "equipment_id": eq_id,
                    "equipment_type": et,
                    "role": role,
                    "median_occupied": round(float(occ_vals.median()), 3) if not occ_vals.empty else None,
                    "median_unoccupied": round(float(unocc_vals.median()), 3) if not unocc_vals.empty else None,
                    "median_all": round(float(num.median()), 3),
                    "n_occupied": int(len(occ_vals)),
                    "n_unoccupied": int(len(unocc_vals)),
                }
            )
    return pd.DataFrame(rows)


def critical_sensor_roles(role_map: dict, frames: dict[str, pd.DataFrame] | None = None) -> set[str]:
    """Union of sweep-sensor roles, rule-required roles present in data, and ``*-sp``.

    Data-model driven: only roles that appear (mapped or alias-resolved) on at
    least one equipment frame are returned when ``frames`` is provided.
    """
    from app.rules.cookbook_catalog import RULES as CANONICAL_RULES
    from app.rules.cookbook_catalog import SWEEP_SENSOR_ROLES

    candidates: set[str] = set(SWEEP_SENSOR_ROLES)
    for rule in CANONICAL_RULES:
        for role in getattr(rule, "required_roles", []) or []:
            candidates.add(str(role))
    # All mapped *-sp roles
    if isinstance(role_map, dict):
        for eq_id, block in role_map.items():
            if not isinstance(block, dict):
                continue
            for role, col in block.items():
                if role in _META_KEYS or not col:
                    continue
                if str(role).endswith("-sp"):
                    candidates.add(str(role))
    if frames is None:
        return candidates
    present: set[str] = set()
    for eq_id, raw in frames.items():
        mapped = apply_role_map(raw, eq_id, role_map)
        role_series = _role_series_for_frame(mapped, _mapped_roles(role_map, eq_id))
        for role in role_series:
            if role in candidates:
                present.add(role)
    return present


def _diurnal_stat_row(
    *,
    eq_id: str,
    et: str,
    role: str,
    source: str,
    day_type: str,
    fan_state: str,
    hour: int,
    values: pd.Series,
) -> dict[str, Any] | None:
    num = pd.to_numeric(values, errors="coerce").dropna()
    if num.empty:
        return None
    return {
        "equipment_id": eq_id,
        "equipment_type": et,
        "role": role,
        "source": source,
        "day_type": day_type,
        "fan_state": fan_state,
        "hour": int(hour),
        "n": int(len(num)),
        "mean": round(float(num.mean()), 3),
        "std": round(float(num.std(ddof=0)), 3) if len(num) > 1 else 0.0,
        "min": round(float(num.min()), 3),
        "p50": round(float(num.quantile(0.5)), 3),
        "max": round(float(num.max()), 3),
    }


def diurnal_profiles(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
) -> pd.DataFrame:
    """24h mean profiles for critical sensors, split by day_type × fan_state.

    Columns: equipment_id, equipment_type, role, source, day_type, fan_state,
    hour, n, mean, std, min, p50, max.

    ``day_type`` ∈ {weekday, weekend, holiday}; ``fan_state`` ∈ {all, on, off}.
    Equipment without operating proof only emits ``fan_state=all`` rows.
    """
    critical = critical_sensor_roles(role_map, frames)
    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = resolve_equipment_type(eq_id, df=raw, role_map=role_map)
        mapped = apply_role_map(raw, eq_id, role_map)
        if not isinstance(mapped.index, pd.DatetimeIndex) or mapped.empty:
            continue
        role_series = _role_series_for_frame(mapped, _mapped_roles(role_map, eq_id))
        crit_roles = {r: role_series[r] for r in role_series if r in critical}
        if not crit_roles:
            continue
        aug = mapped.copy()
        for role, (s, _src) in role_series.items():
            if role not in aug.columns:
                aug[role] = s
        mask, _proof = operating_mask(aug)
        if mask is None:
            mask, _proof = hydronic_operating_mask(aug)
        day_labels = day_type_series(mapped.index)
        hours = pd.Series(mapped.index.hour, index=mapped.index)
        for role, (series, source) in crit_roles.items():
            num = pd.to_numeric(series, errors="coerce")
            for day_type in DAY_TYPES:
                day_mask = day_labels.eq(day_type)
                if not bool(day_mask.any()):
                    continue
                # fan_state slices
                slices: list[tuple[str, pd.Series]] = [("all", day_mask)]
                if mask is not None:
                    on = mask.reindex(mapped.index).fillna(False).astype(bool)
                    slices.append(("on", day_mask & on))
                    slices.append(("off", day_mask & ~on))
                for fan_state, slice_mask in slices:
                    if not bool(slice_mask.any()):
                        continue
                    sub = num.where(slice_mask)
                    for hour in range(24):
                        hour_vals = sub.where(hours.eq(hour))
                        row = _diurnal_stat_row(
                            eq_id=eq_id,
                            et=et,
                            role=role,
                            source=source,
                            day_type=day_type,
                            fan_state=fan_state,
                            hour=hour,
                            values=hour_vals,
                        )
                        if row is not None:
                            rows.append(row)
    cols = [
        "equipment_id",
        "equipment_type",
        "role",
        "source",
        "day_type",
        "fan_state",
        "hour",
        "n",
        "mean",
        "std",
        "min",
        "p50",
        "max",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    return (
        pd.DataFrame(rows, columns=cols)
        .sort_values(["equipment_id", "role", "day_type", "fan_state", "hour"])
        .reset_index(drop=True)
    )


def fdd_findings_table(results: list[RuleResult]) -> pd.DataFrame:
    """Long-format FDD findings — one row per rule × equipment with flattened metrics."""
    rows: list[dict[str, Any]] = []
    for r in results or []:
        metrics = getattr(r, "metrics", None) or {}
        confirmed = False
        if getattr(r, "confirmed_fault", None) is not None:
            try:
                confirmed = bool(r.confirmed_fault.any())
            except Exception:
                confirmed = False
        if str(getattr(r, "status", "")).upper() in {"FAULT", "FAIL", "WARN"}:
            confirmed = True
        row: dict[str, Any] = {
            "rule_id": r.rule_id,
            "equipment_id": r.equipment_id,
            "equipment_type": r.equipment_type,
            "status": r.status,
            "applicable": bool(r.applicable),
            "confirmed_fault": bool(confirmed),
            "fault_hours": r.fault_hours,
            "fault_pct": None if r.rule_id == "OAT-METEO" else r.fault_pct,
            "fault_samples": r.fault_sample_count,
            "sample_count": r.sample_count,
            "missing_roles": ", ".join(r.missing_roles or []),
            "notes": r.notes or "",
        }
        for k, v in metrics.items():
            key = f"metric_{k}"
            if isinstance(v, (list, dict, tuple, set)):
                row[key] = json.dumps(v, default=str)
            elif hasattr(v, "item"):
                try:
                    row[key] = v.item()
                except Exception:
                    row[key] = str(v)
            else:
                row[key] = v
        rows.append(row)
    return pd.DataFrame(rows)


def _safe_slug(value: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", str(value).strip())
    return s.strip("_") or "unknown"


def _safe_ts_name(rule_id: str, equipment_id: str) -> str:
    """Filesystem-safe name for fdd_timeseries/<rule>__<equip>.csv."""
    return f"{_safe_slug(rule_id)}__{_safe_slug(equipment_id)}.csv"


def _equipment_telemetry_relpath(equipment_id: str) -> str:
    return f"telemetry/{_safe_slug(equipment_id)}.csv"


def _should_write_evidence(
    result: RuleResult,
    *,
    profile: ExportProfile,
    selected_evidence: set[tuple[str, str]] | None,
) -> bool:
    status = str(result.status)
    if status in NEVER_TIMESERIES_STATUSES:
        return False
    allow = PROFILE_TIMESERIES_ALLOWLIST.get(profile, frozenset())
    if status in allow:
        return True
    if selected_evidence and (result.rule_id, result.equipment_id) in selected_evidence:
        return True
    return False


def _compact_evidence_frame(
    result: RuleResult,
    *,
    frames: dict[str, pd.DataFrame] | None = None,
    role_map: dict | None = None,
) -> pd.DataFrame | None:
    """Build compact per-rule evidence (fault masks + telemetry reference)."""
    dbg = debug_frame(result)
    index: pd.Index | None = None
    raw = result.raw_fault
    confirmed = result.confirmed_fault
    if dbg is not None and not dbg.empty:
        index = dbg.index
        if raw is None and "raw_fault" in dbg.columns:
            raw = dbg["raw_fault"]
        if confirmed is None and "confirmed_fault" in dbg.columns:
            confirmed = dbg["confirmed_fault"]
    if index is None and raw is not None:
        index = raw.index
    if index is None and confirmed is not None:
        index = confirmed.index
    if index is None and result.plot_series:
        first = next((s for s in result.plot_series.values() if s is not None), None)
        if first is not None:
            index = first.index
    if index is None and frames and result.equipment_id in frames:
        index = frames[result.equipment_id].index
    if index is None:
        return None

    if raw is None:
        raw = pd.Series(0, index=index)
    else:
        raw = raw.reindex(index).fillna(0)
    if confirmed is None:
        confirmed = pd.Series(0, index=index)
    else:
        confirmed = confirmed.reindex(index).fillna(0)

    evidence_cols: list[str] = []
    if result.plot_series:
        evidence_cols.extend(str(k) for k in result.plot_series if result.plot_series[k] is not None)
    if role_map is not None:
        evidence_cols.extend(_mapped_roles(role_map, result.equipment_id))
    # Stable unique order
    seen: set[str] = set()
    ordered_cols: list[str] = []
    for c in evidence_cols:
        if c not in seen:
            seen.add(c)
            ordered_cols.append(c)

    frame = pd.DataFrame(
        {
            "raw_fault": raw.astype(int) if hasattr(raw, "astype") else raw,
            "confirmed_fault": confirmed.astype(int) if hasattr(confirmed, "astype") else confirmed,
            "telemetry_path": _equipment_telemetry_relpath(result.equipment_id),
            "evidence_columns": ",".join(ordered_cols),
            "rule_id": result.rule_id,
            "equipment_id": result.equipment_id,
        },
        index=index,
    )
    if isinstance(frame.index, pd.DatetimeIndex):
        out_df = frame.reset_index()
        first_col = out_df.columns[0]
        if first_col != "timestamp":
            out_df = out_df.rename(columns={first_col: "timestamp"})
        return out_df
    return frame.reset_index(drop=True)


def write_fdd_evidence(
    results: list[RuleResult],
    out_dir: Path,
    *,
    profile: ExportProfile = "summary",
    selected_evidence: set[tuple[str, str]] | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    role_map: dict | None = None,
) -> ExportCounts:
    """Write profile-filtered compact FDD evidence under ``fdd_timeseries/``."""
    if profile not in EXPORT_PROFILES:
        raise ValueError(f"Unknown export profile: {profile!r}")
    ts_dir = Path(out_dir) / "fdd_timeseries"
    written: list[Path] = []
    suppressed: Counter[str] = Counter()
    written_status: Counter[str] = Counter()
    if not results:
        return ExportCounts()

    for r in results:
        status = str(r.status)
        if not _should_write_evidence(r, profile=profile, selected_evidence=selected_evidence):
            suppressed[status] += 1
            continue
        frame = _compact_evidence_frame(r, frames=frames, role_map=role_map)
        if frame is None or frame.empty:
            suppressed[status] += 1
            continue
        ts_dir.mkdir(parents=True, exist_ok=True)
        path = ts_dir / _safe_ts_name(r.rule_id, r.equipment_id)
        frame.to_csv(path, index=False)
        written.append(path)
        written_status[status] += 1

    return ExportCounts(
        written=tuple(written),
        suppressed_status=dict(suppressed),
        written_status=dict(written_status),
    )


def write_fdd_timeseries(
    results: list[RuleResult],
    out_dir: Path,
    *,
    frames: dict[str, pd.DataFrame] | None = None,
    role_map: dict | None = None,
    profile: ExportProfile = "forensic",
    selected_evidence: set[tuple[str, str]] | None = None,
) -> list[Path]:
    """Compatibility wrapper — delegates to :func:`write_fdd_evidence`.

    Defaults to ``forensic`` so direct callers still receive applicable evidence
    CSVs. Bundle export should pass an explicit profile (default ``summary``).
    """
    counts = write_fdd_evidence(
        results,
        out_dir,
        profile=profile,
        selected_evidence=selected_evidence,
        frames=frames,
        role_map=role_map,
    )
    return list(counts.written)


def write_shared_telemetry(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    out_dir: Path,
    *,
    profile: ExportProfile = "summary",
) -> dict[str, Path]:
    """Write one shared telemetry CSV per equipment under ``telemetry/``.

    * summary — timestamp + mapped roles only
    * diagnostic — mapped roles (same as summary; evidence lives in fdd_timeseries)
    * forensic — mapped roles plus remaining processed frame columns
    """
    if profile not in EXPORT_PROFILES:
        raise ValueError(f"Unknown export profile: {profile!r}")
    tel_dir = Path(out_dir) / "telemetry"
    written: dict[str, Path] = {}
    if not frames:
        return written

    for eq_id in sorted(frames):
        raw = frames[eq_id]
        if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
            continue
        mapped = apply_role_map(raw, eq_id, role_map)
        roles = _mapped_roles(role_map, eq_id)
        cols: list[str] = []
        for role in roles:
            if role in mapped.columns:
                cols.append(role)
        if profile == "forensic":
            for col in mapped.columns:
                c = str(col)
                if c not in cols and c not in _META_KEYS:
                    cols.append(c)
            # Also include unmapped raw columns present on the source frame.
            for col in raw.columns:
                c = str(col)
                if c not in cols and c not in _META_KEYS:
                    cols.append(c)

        if not cols and not isinstance(mapped.index, pd.DatetimeIndex):
            continue

        data: dict[str, Any] = {}
        if isinstance(mapped.index, pd.DatetimeIndex):
            data["timestamp"] = mapped.index
            index = None
        else:
            index = mapped.index
        for c in cols:
            if c in mapped.columns:
                data[c] = mapped[c].to_numpy() if index is None else mapped[c]
            elif c in raw.columns:
                series = raw[c]
                if index is None and isinstance(mapped.index, pd.DatetimeIndex):
                    data[c] = series.reindex(mapped.index).to_numpy()
                else:
                    data[c] = series
        if not data:
            continue
        out_df = pd.DataFrame(data)
        # Ensure a single timestamp column at position 0 when present.
        if "timestamp" in out_df.columns:
            ordered = ["timestamp"] + [c for c in out_df.columns if c != "timestamp"]
            out_df = out_df.loc[:, ordered]
        tel_dir.mkdir(parents=True, exist_ok=True)
        path = tel_dir / f"{_safe_slug(eq_id)}.csv"
        out_df.to_csv(path, index=False)
        written[eq_id] = path
    return written


WATTLAB_README = """# WattLab dump — vibe19 → vibe20 handoff

This bundle is the "big dump" consumed by WattLab (vibe_code_apps_20) so an AI
agent can seed, calibrate, and iterate an EnergyPlus digital twin. All tables
are data-model driven: only points mapped in `role_map.yaml` appear.

Start with **`MANIFEST.json`** — every file's path, columns, purpose, and
how the agent should use it.

## Model seed (data-derived)
- `model_seed.json` — building id, inferred schedules, data window. Geometry /
  building_type / floor_area / utility bills are tagged `user_required` for the
  vibe20 human+agent to fill. No interactive Energy Model wizard in vibe19.
- `schedule_inference.json` / `schedule_inference_table.csv` — inferred
  occupied/operating schedules per equipment.
- `operating_signatures.csv` — OAT-binned operating signatures (the
  spreadsheet "Weather Man" equivalent, from observed data).
- `weather_observed.csv` — observed weather (web/Open-Meteo enriched) for
  AMY-style EPW construction and bin tables.

## FDD faults (every rule ran)
- `fdd_summary.csv` — aggregate cookbook rule results (one row per rule × equip).
- `fdd_findings.csv` — long-format findings with flattened metrics + confirmed_fault.
- `fdd_timeseries/<rule_id>__<equipment_id>.csv` — per-rule fault masks
  (`raw_fault`, `confirmed_fault`) plus key metric series. Lazy-load via MANIFEST.
- `fault_settings.json` — tunable parameters used for the run.

## Run hours and mechanical cooling
- `motor_hours.csv` / `motor_weekly.csv` — motor run hours per equipment.
- `mech_cooling_oat_bins.csv` — mechanical cooling hours by OAT bin per device,
  plus aggregated `ALL` rows.
- `mech_cooling_coverage.csv` — every cooling-capable device with
  included/excluded status and the run proof used (or reason excluded).
- `economizer_weather.csv` — economizer opportunity / compliance hours.

## Sensors, setpoints, diurnal profiles
- `sensor_stats_all.csv` — summary stats for every mapped role per equipment.
- `sensor_stats_fan_on.csv` / `sensor_stats_fan_off.csv` — the same stats
  sliced by fan/pump operating proof (equipment without proof only appears
  in `all`).
- `sensor_diurnal_24h.csv` — critical sensors (sweep + rule-required + `*-sp`)
  binned by hour-of-day, split by `day_type` (weekday/weekend/holiday) and
  `fan_state` (all/on/off). Filter columns to get separate datasets.
- `setpoints.csv` — occupied/unoccupied medians for every `*-sp` role.

## Analytic-tab CSVs
- `topology.csv` / `data_model.csv` — equipment feeds/fedBy and point bindings.
- `sensor_health_matrix.csv` / `sensor_fault_summary.csv` — SV-* health.
- `rcx_preset_coverage.csv` / `rcx_zone_comfort_ranking.csv` — RCx coverage.
- `meter_monthly_electric.csv` / `meter_monthly_gas.csv` — monthly meters.
- `role_map_gap_report.csv` — unmapped/missing roles worth fixing.

## Session round-trip
- `session_config.json` + `role_map.yaml` (+ `column_map.json`) reload this
  exact session in the vibe19 app.
- `run_report.json` — status counts and package health.
"""


def write_wattlab_readme(out_dir) -> Path:
    p = Path(out_dir) / "README_WATTLAB.md"
    p.write_text(WATTLAB_README, encoding="utf-8")
    return p


# Static purpose/how_to_use hints keyed by logical artifact name
_MANIFEST_HINTS: dict[str, dict[str, str]] = {
    "MANIFEST.json": {
        "kind": "manifest",
        "purpose": "Index of every file in this dump",
        "how_to_use": "Read first; discover paths/columns before loading CSVs",
    },
    "README_WATTLAB.md": {
        "kind": "docs",
        "purpose": "Human-readable dump guide",
        "how_to_use": "Skim for agent onboarding",
    },
    "model_seed.json": {
        "kind": "seed",
        "purpose": "Data-derived building seed (data_window, schedule_hints)",
        "how_to_use": "Start here for calibration; fill field_sources marked user_required",
    },
    "fdd_summary.csv": {
        "kind": "fdd",
        "purpose": "Aggregate FDD results per rule × equipment",
        "how_to_use": "Bridge to ECM suggestions; filter status=FAULT / fault_hours>0",
    },
    "fdd_findings.csv": {
        "kind": "fdd",
        "purpose": "Long-format findings with flattened metrics",
        "how_to_use": "Primary agent table for iterating EnergyPlus controls assumptions",
    },
    "fdd_timeseries": {
        "kind": "fdd_timeseries",
        "purpose": "Per-rule fault masks + plot series",
        "how_to_use": "Lazy-load only the rules you are calibrating against",
    },
    "sensor_diurnal_24h.csv": {
        "kind": "sensor",
        "purpose": "24h critical-sensor profiles by day_type × fan_state",
        "how_to_use": "Filter day_type/fan_state; use for schedule and setpoint calibration",
    },
    "sensor_stats_all.csv": {
        "kind": "sensor",
        "purpose": "Summary stats for every mapped role",
        "how_to_use": "Sanity-check zone/SAT/plant operating ranges",
    },
    "sensor_stats_fan_on.csv": {
        "kind": "sensor",
        "purpose": "Stats while fan/pump proof is ON",
        "how_to_use": "Prefer for occupied/operating setpoints and SAT",
    },
    "sensor_stats_fan_off.csv": {
        "kind": "sensor",
        "purpose": "Stats while fan/pump proof is OFF",
        "how_to_use": "Detect night setback / unoccupied drift",
    },
    "setpoints.csv": {
        "kind": "sensor",
        "purpose": "Occupied/unoccupied setpoint medians",
        "how_to_use": "Seed EnergyPlus schedule setpoints",
    },
    "operating_signatures.csv": {
        "kind": "signature",
        "purpose": "OAT-binned fan / mech-cooling on-fractions",
        "how_to_use": "Calibrate prototype operating curves",
    },
    "weather_observed.csv": {
        "kind": "weather",
        "purpose": "Observed weather for AMY EPW",
        "how_to_use": "Required for non-dry-run calibration",
    },
    "motor_weekly.csv": {
        "kind": "runtime",
        "purpose": "Weekly motor run hours",
        "how_to_use": "Evidence for schedule-align ECMs",
    },
    "economizer_weather.csv": {
        "kind": "runtime",
        "purpose": "Economizer opportunity / compliance",
        "how_to_use": "Evidence for chiller lockout / economizer ECMs",
    },
}


def build_manifest(
    written: dict[str, Path],
    out_dir: Path,
    *,
    profile: ExportProfile | None = None,
    export_counts: ExportCounts | None = None,
) -> dict[str, Any]:
    """Build a MANIFEST.json describing every emitted file."""
    out = Path(out_dir)
    files: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _entry(rel: str, kind: str, purpose: str, how: str, columns: list[str] | None = None) -> dict[str, Any]:
        return {
            "path": rel,
            "kind": kind,
            "columns": columns or [],
            "purpose": purpose,
            "how_to_use": how,
        }

    # Timeseries directory as a single logical entry plus per-file listing
    ts_paths = sorted(p for k, p in written.items() if str(k).startswith("fdd_timeseries"))
    if ts_paths or (out / "fdd_timeseries").is_dir():
        hint = _MANIFEST_HINTS["fdd_timeseries"]
        files.append(
            _entry(
                "fdd_timeseries/",
                hint["kind"],
                hint["purpose"],
                hint["how_to_use"],
                ["timestamp", "raw_fault", "confirmed_fault", "<plot_series...>"],
            )
        )
        for p in sorted((out / "fdd_timeseries").glob("*.csv")) if (out / "fdd_timeseries").is_dir() else ts_paths:
            rel = p.relative_to(out).as_posix() if p.is_absolute() else str(p)
            if rel in seen:
                continue
            seen.add(rel)
            cols: list[str] = []
            try:
                cols = list(pd.read_csv(p, nrows=0).columns)
            except Exception:
                cols = ["timestamp", "raw_fault", "confirmed_fault"]
            files.append(
                _entry(rel, "fdd_timeseries_file", f"Timeseries for {p.stem}", hint["how_to_use"], cols)
            )

    # Shared telemetry directory
    tel_root = out / "telemetry"
    if tel_root.is_dir() or any(str(k).startswith("telemetry") for k in written):
        files.append(
            _entry(
                "telemetry/",
                "telemetry",
                "Shared equipment telemetry referenced by FDD evidence",
                "Load once per equipment; join via fdd_timeseries.telemetry_path",
                ["timestamp", "<mapped_roles...>"],
            )
        )
        for p in sorted(tel_root.glob("*.csv")) if tel_root.is_dir() else []:
            rel = p.relative_to(out).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            cols: list[str] = []
            try:
                cols = list(pd.read_csv(p, nrows=0).columns)
            except Exception:
                cols = ["timestamp"]
            files.append(
                _entry(rel, "telemetry_file", f"Telemetry for {p.stem}", "Join from evidence telemetry_path", cols)
            )

    for key, path in sorted(written.items(), key=lambda kv: str(kv[1])):
        if (
            str(key).startswith("fdd_timeseries")
            or str(key).startswith("telemetry")
            or str(key).startswith("bootstrap:")
        ):
            continue
        p = Path(path)
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(out).as_posix()
        except ValueError:
            rel = p.name
        if rel in seen:
            continue
        seen.add(rel)
        name = p.name
        hint = _MANIFEST_HINTS.get(name) or _MANIFEST_HINTS.get(key) or {
            "kind": "artifact",
            "purpose": key,
            "how_to_use": "Optional supporting table",
        }
        columns: list[str] = []
        if p.suffix.lower() == ".csv":
            try:
                columns = list(pd.read_csv(p, nrows=0).columns)
            except Exception:
                columns = []
        files.append(_entry(rel, hint["kind"], hint["purpose"], hint["how_to_use"], columns))

    # Ensure MANIFEST / README are described even before they are written
    for name in ("MANIFEST.json", "README_WATTLAB.md"):
        if name not in seen:
            hint = _MANIFEST_HINTS[name]
            files.insert(0, _entry(name, hint["kind"], hint["purpose"], hint["how_to_use"]))
            seen.add(name)

    payload: dict[str, Any] = {
        "product": "OpenFDD WattLab Dump",
        "schema_version": "wattlab_dump_v2",
        "file_count": len(files),
        "files": files,
    }
    if profile is not None:
        payload["export_profile"] = profile
    if export_counts is not None:
        payload["export_counts"] = {
            "written": len(export_counts.written),
            "suppressed_status": dict(export_counts.suppressed_status),
            "written_status": dict(export_counts.written_status),
        }
    return payload


def write_manifest(
    out_dir,
    written: dict[str, Path],
    *,
    profile: ExportProfile | None = None,
    export_counts: ExportCounts | None = None,
) -> Path:
    out = Path(out_dir)
    payload = build_manifest(written, out, profile=profile, export_counts=export_counts)
    path = out / "MANIFEST.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


__all__ = [
    "ExportProfile",
    "EXPORT_PROFILES",
    "NEVER_TIMESERIES_STATUSES",
    "PROFILE_TIMESERIES_ALLOWLIST",
    "ExportCounts",
    "sensor_stats_tables",
    "setpoints_table",
    "critical_sensor_roles",
    "diurnal_profiles",
    "fdd_findings_table",
    "write_fdd_evidence",
    "write_fdd_timeseries",
    "write_shared_telemetry",
    "write_wattlab_readme",
    "build_manifest",
    "write_manifest",
    "WATTLAB_README",
]
