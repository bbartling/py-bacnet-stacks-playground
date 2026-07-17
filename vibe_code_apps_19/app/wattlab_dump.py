"""WattLab dump helpers — sensor stats and setpoint tables for the vibe20 handoff.

These build the "big dump" pieces of the agent bundle: per-equipment summary
statistics of every mapped role sliced by operating state (all / fan-or-pump
on / off) and occupied/unoccupied medians of every setpoint (``*-sp``) role.
Everything is data-model driven — only roles present in the role map are used.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.column_map_json import POINT_DISPLAY, canonicalize_point
from app.occupancy import OccupancySchedule, occupied_mask
from app.rcx_plots import hydronic_operating_mask, operating_mask
from app.role_map import apply_role_map
from app.site_model import resolve_equipment_type

# role_map meta keys that are not timeseries roles
_META_KEYS = {"chw_pump_equipment", "notes", "equipment_type", "plant_group"}


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


WATTLAB_README = """# WattLab dump — vibe19 → vibe20 handoff

This bundle is the "big dump" consumed by WattLab (vibe_code_apps_20) to seed,
calibrate, and crosscheck an EnergyPlus digital twin. All tables are data-model
driven: only points mapped in `role_map.yaml` appear.

## Model seed
- `model_seed.json` — building id, inferred schedules, data window, city/lat/lon,
  utility bills (when provided). Start here.
- `schedule_inference.json` / `schedule_inference_table.csv` — inferred
  occupied/operating schedules per equipment.
- `operating_signatures.csv` — OAT-binned operating signatures (the
  spreadsheet "Weather Man" equivalent, from observed data).
- `weather_observed.csv` — observed weather (web/Open-Meteo enriched) for
  AMY-style EPW construction and bin tables.

## Run hours and mechanical cooling
- `motor_hours.csv` / `motor_weekly.csv` — motor run hours per equipment.
- `mech_cooling_oat_bins.csv` — mechanical cooling hours by OAT bin per device,
  plus aggregated `ALL` rows.
- `mech_cooling_coverage.csv` — every cooling-capable device with
  included/excluded status and the run proof used (or reason excluded).

## Sensors and setpoints
- `sensor_stats_all.csv` — summary stats for every mapped role per equipment.
- `sensor_stats_fan_on.csv` / `sensor_stats_fan_off.csv` — the same stats
  sliced by fan/pump operating proof (equipment without proof only appears
  in `all`).
- `setpoints.csv` — occupied/unoccupied medians for every `*-sp` role.

## Faults and diagnostics
- `fdd_summary.csv` — cookbook rule results summary.
- `fault_settings.json` — tunable parameters used for the run.
- `rcx_preset_coverage.csv` — which RCx plots have data.
- `role_map_gap_report.csv` — unmapped/missing roles worth fixing.

## Session round-trip
- `session_config.json` + `role_map.yaml` (+ `column_map.json`) reload this
  exact session in the vibe19 app.
"""


def write_wattlab_readme(out_dir) -> Any:
    from pathlib import Path

    p = Path(out_dir) / "README_WATTLAB.md"
    p.write_text(WATTLAB_README, encoding="utf-8")
    return p
