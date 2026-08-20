"""Track C: one aggregated W2A per EnergyPlus thermal zone. Not SequentialLoad clones."""
from __future__ import annotations

from typing import Any

from eplus_gym.idf_diagnostics import count_w2a_objects
from eplus_gym.idf_objects import field_by_comment, iter_objects, normalize_idf, replace_comment_field
from eplus_gym.trackb_banks import (
    CLG_TYPE,
    CURVE_PROVENANCE,
    FAN_TYPE,
    HP_COUNT_67_NINE,
    HTG_TYPE,
    ZONEHVAC_TYPE,
    rewrite_parent_coils_to_autosize,
)
from eplus_native.idf_inspect import NINE_ZONES

PUBLIC_LABEL = (
    "TRACK_C ONE_W2A_PER_ZONE AGGREGATE — NOT AS-BUILT — NOT 67 IDENTICAL UNITS"
)
TRACK_C3_SKIP_REASON = (
    "C3 VariableSpeedEquationFit skipped: inherited A04 EquationFit curves are unverified "
    "and no valid multi-speed manufacturer performance points are available"
)
C2_HEATING_W = {
    "low": 675_000.0,
    "base": 800_000.0,
    "high": 940_000.0,
}
SCREENING_HEATING_W = (675_000.0, 940_000.0)


def one_w2a_per_zone_ok(src: str) -> bool:
    counts = count_w2a_objects(src)
    return counts["n_heating_coils"] == 9 and counts["n_zonehvac"] == 9


def allocate_heating_by_inventory(total_w: float, counts: dict[str, int] | None = None) -> dict[str, float]:
    hp = dict(counts or HP_COUNT_67_NINE)
    n = float(sum(hp.values()))
    if n <= 0:
        raise ValueError("hp inventory sum must be positive")
    return {z: float(total_w) * float(hp[z]) / n for z in NINE_ZONES}


def trackc3_allowed(*, valid_speed_points: int) -> bool:
    return int(valid_speed_points) >= 2


def freeze_explicit_from_eio(src: str, totals: dict[str, dict[str, Any]]) -> str:
    text = normalize_idf(src)
    for z in NINE_ZONES:
        row = totals[z]
        htg = None
        for block in iter_objects(text, HTG_TYPE):
            if field_by_comment(block, "Name") == f"{z} WAHP Heating Coil":
                htg = block
                break
        if htg is None:
            raise ValueError(f"missing heating coil for {z}")
        new = replace_comment_field(htg, "Rated Heating Capacity", f"{float(row['heating_capacity_w']):.6g}")
        if row.get("heating_airflow_m3s"):
            new = replace_comment_field(new, "Rated Air Flow Rate", f"{float(row['heating_airflow_m3s']):.6g}")
        if row.get("heating_water_m3s"):
            try:
                new = replace_comment_field(new, "Rated Water Flow Rate", f"{float(row['heating_water_m3s']):.6g}")
            except ValueError:
                pass
        text = text.replace(htg, new, 1)
    return text


def hard_size_heating(src: str, *, sensitivity: str = "base") -> str:
    target = C2_HEATING_W[sensitivity]
    alloc = allocate_heating_by_inventory(target)
    text = normalize_idf(src)
    for z in NINE_ZONES:
        for block in iter_objects(text, HTG_TYPE):
            if field_by_comment(block, "Name") != f"{z} WAHP Heating Coil":
                continue
            new = replace_comment_field(block, "Rated Heating Capacity", f"{alloc[z]:.6g}")
            text = text.replace(block, new, 1)
            break
    return text


def trackc_plan(*, sensitivity: str = "base") -> dict[str, Any]:
    return {
        "schema": "vibe22.trackc.one_w2a.v1",
        "public_label": PUBLIC_LABEL,
        "as_built": False,
        "topology": "one_aggregated_w2a_per_thermal_zone",
        "sequential_load_clones": False,
        "control_groups": 6,
        "thermal_zones": 9,
        "sensitivity": sensitivity,
        "c2_heating_w": dict(C2_HEATING_W),
        "screening_heating_w": list(SCREENING_HEATING_W),
        "curve_provenance": CURVE_PROVENANCE,
        "c3_allowed": False,
        "c3_skip_reason": TRACK_C3_SKIP_REASON,
        "hp_count_records": dict(HP_COUNT_67_NINE),
        "identical_physical_units_proven": False,
    }


def prepare_c1_autosize_parent(src: str) -> tuple[str, dict[str, Any]]:
    return rewrite_parent_coils_to_autosize(src)
