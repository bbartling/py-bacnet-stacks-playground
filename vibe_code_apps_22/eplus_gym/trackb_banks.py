"""Track B capacity-class banks. Not as-built. Not 67 identical 3-ton units."""
from __future__ import annotations

from typing import Any

from eplus_gym.idf_objects import field_by_comment, find_named_object, iter_objects, replace_comment_field
from eplus_native.idf_inspect import NINE_ZONES
from eplus_native.six_zone_htg_stage import ACTION_KEYS, ACTION_TO_BAS

PUBLIC_LABEL = (
    "PRELIMINARY CAPACITY-CLASS ARCHETYPE CONSTRAINED BY THE 67-UNIT BAS INVENTORY"
)
HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"
ZONEHVAC_TYPE = "ZoneHVAC:WaterToAirHeatPump"

# BAS six-group inventory (thermal_zone_model). Counts, not nameplates.
BAS_SIX_HP = {
    "1F_Area_A": 15,
    "1F_Area_B": 10,
    "1F_Area_C": 11,
    "1F_Area_D": 10,
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
HP_COUNT_67_NINE = {
    "1F_Library_IMC": 2,
    "1F_Cafe_Kitchen": 3,
    "1F_Gym": 4,
    "1F_Area_A": 13,
    "1F_Area_B": 10,
    "1F_Area_C": 8,
    "1F_Area_D": 6,
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
ALLOCATION = {
    "base": {"small": 0.25, "medium": 0.50, "large": 0.25},
    "low": {"small": 0.40, "medium": 0.40, "large": 0.20},
    "high": {"small": 0.15, "medium": 0.35, "large": 0.50},
}
CURVE_PROVENANCE = {
    "heating_equationfit": "inherited_from_a04_parent_unverified_catalog",
    "not_as_built": True,
    "tonnage_asserted": False,
}


def n_banks_for_hp_count(n_hp: int) -> int:
    """Staging banks from inventory diversity, not one giant coil and not 67 clones."""
    n = int(n_hp)
    if n <= 0:
        raise ValueError("hp count must be positive")
    if n <= 4:
        return 2
    if n <= 10:
        return 2
    if n <= 14:
        return 3
    return 3


def bank_labels(n_banks: int) -> list[str]:
    if n_banks == 2:
        return ["small", "large"]
    if n_banks == 3:
        return ["small", "medium", "large"]
    raise ValueError(f"unsupported n_banks={n_banks}")


def fractions_for(n_banks: int, *, sensitivity: str = "base") -> dict[str, float]:
    raw = dict(ALLOCATION[sensitivity])
    labels = bank_labels(n_banks)
    picked = {k: float(raw[k]) for k in labels}
    s = sum(picked.values())
    return {k: v / s for k, v in picked.items()}


def split_autosized_total(total_w: float, fractions: dict[str, float]) -> dict[str, float]:
    if total_w <= 0:
        raise ValueError("autosized total must be positive before split")
    return {k: float(total_w) * float(v) for k, v in fractions.items()}


def six_group_plan(*, sensitivity: str = "base") -> dict[str, Any]:
    groups = []
    for key in ACTION_KEYS:
        bas = ACTION_TO_BAS[key]
        n_hp = BAS_SIX_HP[bas]
        n_banks = n_banks_for_hp_count(n_hp)
        groups.append(
            {
                "action_key": key,
                "bas_group": bas,
                "hp_count": n_hp,
                "n_banks": n_banks,
                "fractions": fractions_for(n_banks, sensitivity=sensitivity),
                "tonnage_asserted": False,
            }
        )
    return {
        "public_label": PUBLIC_LABEL,
        "as_built": False,
        "assumes_identical_3ton": False,
        "sensitivity": sensitivity,
        "hp_count_sum": sum(BAS_SIX_HP.values()),
        "groups": groups,
        "curve_provenance": CURVE_PROVENANCE,
        "control_groups": 6,
        "equipment_representation": "multiple_equationfit_banks_per_group",
    }


def nine_zone_plan(*, sensitivity: str = "base") -> dict[str, Any]:
    zones = []
    for z in NINE_ZONES:
        n_hp = HP_COUNT_67_NINE[z]
        n_banks = n_banks_for_hp_count(n_hp)
        zones.append(
            {
                "eplus_zone": z,
                "hp_count": n_hp,
                "n_banks": n_banks,
                "fractions": fractions_for(n_banks, sensitivity=sensitivity),
            }
        )
    return {"zones": zones, "sensitivity": sensitivity, "public_label": PUBLIC_LABEL}


def clone_heating_coil_banks(block: str, *, n_banks: int, zone: str) -> list[str]:
    """Duplicate one EquationFit coil into autosized banks with unique names."""
    name = field_by_comment(block, "Name")
    if not name:
        raise ValueError("coil missing Name")
    out = []
    for i, label in enumerate(bank_labels(n_banks), start=1):
        cloned = block.replace(name, f"{zone} WAHP Heating Coil {label}", 1)
        cloned = replace_comment_field(cloned, "Rated Heating Capacity", "Autosize")
        cloned = replace_comment_field(cloned, "Rated Air Flow Rate", "Autosize")
        out.append(cloned)
        _ = i
    return out


def scored_runtime_w2a_pass(gate: dict[str, Any]) -> bool:
    phase = gate.get("w2a_low_airflow_by_phase") or {}
    return int(phase.get("scored_runtime") or 0) == 0 and int(gate.get("severe_count") or 0) == 0 and int(
        gate.get("fatal_count") or 0
    ) == 0


def champion_gates_template() -> dict[str, Any]:
    return {
        "schema": "vibe22.trackb.champion_gates.v1",
        "public_label": PUBLIC_LABEL,
        "long_campaign_allowed": False,
        "gates": {
            "energyplus_success": "not_run",
            "zero_severe_fatal": "not_run",
            "zero_scored_runtime_w2a": "not_run",
            "six_zone_actuation": "not_run",
            "transient_train_dev": "not_run",
            "transient_model_selection_val": "not_run",
            "partial_period_monthly_gl14_style": "not_run",
            "load_shape_published": False,
            "valid_native_aggregated_demand": False,
            "observed_bas_incumbent_replay": False,
            "heldout_after_selection": "locked_unseen",
        },
        "ramp_threshold_role": "internal_plausibility_screen_not_ashrae_validation",
        "champion": None,
    }
