"""Track B capacity-class banks. Not as-built. Not 67 identical 3-ton units."""
from __future__ import annotations

from typing import Any

from eplus_gym.idf_objects import (
    field_by_comment,
    find_named_object,
    iter_objects,
    normalize_idf,
    replace_comment_field,
)
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


CURVE_TOKENS = (
    "HtgCapCurve",
    "HtgPowCurve",
    "HtgPLFCurve",
    "ClgTotCapCurve",
    "ClgSensCapCurve",
    "ClgPowCurve",
    "ClgPLFCurve",
)
CLG_TYPE = "Coil:Cooling:WaterToAirHeatPump:EquationFit"
FAN_TYPE = "Fan:OnOff"
OA_MIX_TYPE = "OutdoorAir:Mixer"
OA_NODE_TYPE = "OutdoorAir:Node"
SUPP_TYPE = "Coil:Heating:Electric"
BRANCH_TYPE = "Branch"
EQUIP_LIST_TYPE = "ZoneHVAC:EquipmentList"
EQUIP_CONN_TYPE = "ZoneHVAC:EquipmentConnections"


def wahp_label_name(name: str, zone: str, label: str) -> str:
    token = f"{zone} WAHP"
    if name.startswith(token):
        return name.replace(token, f"{zone} WAHP {label}", 1)
    if name.startswith(zone):
        return f"{name} {label}"
    return f"{name} {label}"


def _relabel_wahp_block(block: str, zone: str, label: str) -> str:
    cloned = block.replace(f"{zone} WAHP", f"{zone} WAHP {label}")
    for token in CURVE_TOKENS:
        cloned = cloned.replace(f"{zone} WAHP {label} {token}", f"{zone} WAHP {token}")
    return cloned


def clone_heating_coil_banks(
    block: str,
    *,
    n_banks: int,
    zone: str,
    heating_total_w: float,
    air_total_m3s: float,
    water_total_m3s: float | None = None,
    fractions: dict[str, float] | None = None,
) -> list[str]:
    """Duplicate one EquationFit coil into explicit-fraction banks. Never independent Autosize."""
    name = field_by_comment(block, "Name")
    if not name:
        raise ValueError("coil missing Name")
    fr = fractions or fractions_for(n_banks)
    caps = split_autosized_total(float(heating_total_w), fr)
    airs = split_autosized_total(float(air_total_m3s), fr)
    waters = split_autosized_total(float(water_total_m3s), fr) if water_total_m3s else None
    out = []
    for label in bank_labels(n_banks):
        cloned = _relabel_wahp_block(block, zone, label)
        cloned = replace_comment_field(cloned, "Rated Heating Capacity", f"{caps[label]:.6g}")
        cloned = replace_comment_field(cloned, "Rated Air Flow Rate", f"{airs[label]:.6g}")
        if waters is not None:
            try:
                cloned = replace_comment_field(cloned, "Rated Water Flow Rate", f"{waters[label]:.6g}")
            except ValueError:
                pass
        out.append(cloned)
    return out


def parent_numeric_or_none(block: str, comment: str) -> float | None:
    raw = field_by_comment(block, comment)
    if raw is None or str(raw).strip() == "" or str(raw).lower() == "autosize":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def structural_fixture_totals(src: str) -> dict[str, dict[str, Any]]:
    """Numeric parent capacity + labeled placeholder airflow until LIVE eio exists."""
    totals = default_sizing_totals_from_parent(src)
    for _z, row in totals.items():
        if not row.get("heating_capacity_w"):
            raise ValueError("parent heating capacity missing; refuse fabricated watts")
        if not row.get("heating_airflow_m3s"):
            row["heating_airflow_m3s"] = 1.0
            row["provenance"] = "structural_placeholder_airflow_pending_live_eio"
        if not row.get("cooling_airflow_m3s"):
            row["cooling_airflow_m3s"] = row["heating_airflow_m3s"]
    return totals


def rewrite_parent_coils_to_autosize(src: str) -> tuple[str, dict[str, Any]]:
    """Child-only rewrite. Never overwrite A04. User-specified 149430 W is not autosized."""
    text = normalize_idf(src)
    n = 0
    for obj_type, fields in (
        (HTG_TYPE, ("Rated Heating Capacity", "Rated Air Flow Rate", "Rated Water Flow Rate")),
        (
            CLG_TYPE,
            (
                "Rated Total Cooling Capacity",
                "Rated Sensible Cooling Capacity",
                "Rated Air Flow Rate",
                "Rated Water Flow Rate",
            ),
        ),
        (FAN_TYPE, ("Maximum Flow Rate",)),
        (
            ZONEHVAC_TYPE,
            (
                "Supply Air Flow Rate During Heating Operation",
                "Supply Air Flow Rate During Cooling Operation",
                "Supply Air Flow Rate When No Cooling or Heating is Needed",
                "Heating Supply Air Flow Rate",
                "Cooling Supply Air Flow Rate",
                "No Load Supply Air Flow Rate",
            ),
        ),
    ):
        for block in iter_objects(text, obj_type):
            new = block
            changed = False
            for field in fields:
                raw = field_by_comment(block, field)
                if raw is None:
                    continue
                if str(raw).strip().lower() == "autosize":
                    continue
                try:
                    new = replace_comment_field(new, field, "Autosize")
                    changed = True
                    n += 1
                except ValueError:
                    continue
            if changed:
                text = text.replace(block, new, 1)
    return text, {
        "n_fields_rewritten": n,
        "not_a04_overwrite": True,
        "user_specified_149430_not_treated_as_autosized": True,
        "curve_provenance": CURVE_PROVENANCE,
    }


def default_sizing_totals_from_parent(src: str) -> dict[str, dict[str, Any]]:
    """Use parent numeric fields when present. Airflow Autosize is not a live total."""
    out: dict[str, dict[str, Any]] = {}
    for z in NINE_ZONES:
        htg = find_named_object(src, HTG_TYPE, f"{z} WAHP Heating Coil")
        clg = find_named_object(src, CLG_TYPE, f"{z} WAHP Cooling Coil")
        if not htg:
            raise ValueError(f"missing parent heating coil for {z}")
        h_w = parent_numeric_or_none(htg, "Rated Heating Capacity")
        h_air = parent_numeric_or_none(htg, "Rated Air Flow Rate")
        h_wtr = parent_numeric_or_none(htg, "Rated Water Flow Rate")
        c_w = parent_numeric_or_none(clg, "Rated Total Cooling Capacity") if clg else None
        c_air = parent_numeric_or_none(clg, "Rated Air Flow Rate") if clg else None
        c_wtr = parent_numeric_or_none(clg, "Rated Water Flow Rate") if clg else None
        out[z] = {
            "heating_capacity_w": h_w,
            "heating_airflow_m3s": h_air,
            "heating_water_m3s": h_wtr,
            "cooling_capacity_w": c_w,
            "cooling_airflow_m3s": c_air,
            "cooling_water_m3s": c_wtr,
            "provenance": "parent_numeric_fields_not_live_eio" if h_w else "missing_numeric_parent",
        }
    return out


def parse_eio_component_sizing(eio_text: str) -> dict[str, dict[str, Any]]:
    """Parse EnergyPlus eio Component Sizing Information rows."""
    out: dict[str, dict[str, float]] = {}
    for raw in eio_text.splitlines():
        if "Component Sizing Information" not in raw:
            continue
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 5:
            continue
        obj_type, obj_name, field, value = parts[1], parts[2], parts[3], parts[4]
        try:
            num = float(value)
        except ValueError:
            continue
        rec = out.setdefault(obj_name, {"object_type": obj_type})
        key = field.lower()
        if "rated heating capacity" in key or "design size rated heating capacity" in key:
            rec["heating_capacity_w"] = num
            rec["heating_capacity_user_specified"] = "user-specified" in key
        elif "rated total cooling capacity" in key:
            rec["cooling_capacity_w"] = num
        elif "rated air flow" in key and "heating" in obj_type.lower():
            rec["heating_airflow_m3s"] = num
        elif "rated air flow" in key:
            rec.setdefault("airflow_m3s", num)
        elif "rated water flow" in key and "heating" in obj_type.lower():
            rec["heating_water_m3s"] = num
        elif "rated water flow" in key:
            rec.setdefault("water_m3s", num)
    return out


def _eio_lookup(parsed: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    """EnergyPlus 26.1 eio uppercases object names; IDF mixed-case still matches."""
    if name in parsed:
        return parsed[name]
    want = name.casefold()
    for key, rec in parsed.items():
        if key.casefold() == want:
            return rec
    return {}


def sizing_totals_from_eio(eio_text: str) -> dict[str, dict[str, Any]]:
    parsed = parse_eio_component_sizing(eio_text)
    out: dict[str, dict[str, Any]] = {}
    for z in NINE_ZONES:
        htg = _eio_lookup(parsed, f"{z} WAHP Heating Coil")
        clg = _eio_lookup(parsed, f"{z} WAHP Cooling Coil")
        h_w = htg.get("heating_capacity_w")
        h_air = htg.get("heating_airflow_m3s") or htg.get("airflow_m3s")
        if not h_w or not h_air:
            raise ValueError(f"LIVE eio missing heating capacity/airflow for {z}")
        cap_src = "user_specified" if htg.get("heating_capacity_user_specified") else "design_size"
        out[z] = {
            "heating_capacity_w": float(h_w),
            "heating_airflow_m3s": float(h_air),
            "heating_water_m3s": htg.get("heating_water_m3s") or htg.get("water_m3s"),
            "cooling_capacity_w": clg.get("cooling_capacity_w"),
            "cooling_airflow_m3s": clg.get("airflow_m3s") or h_air,
            "cooling_water_m3s": clg.get("water_m3s"),
            "heating_capacity_source": cap_src,
            "provenance": "live_energyplus_eio_component_sizing",
        }
    return out


def _replace_block(src: str, old: str, new: str) -> str:
    text = normalize_idf(src)
    needle = normalize_idf(old)
    if needle not in text:
        raise ValueError("IDF block to replace not found")
    return text.replace(needle, new, 1)


def _expand_name_line(block: str, old_name: str, new_names: list[str]) -> str:
    lines = block.splitlines(keepends=True)
    out: list[str] = []
    found = False
    for line in lines:
        left = line.split("!", 1)[0]
        if (not found) and old_name in left:
            found = True
            for i, nm in enumerate(new_names):
                nl = line.replace(old_name, nm, 1)
                if i < len(new_names) - 1 and ";" in nl.split("!", 1)[0]:
                    nl = nl.replace(";", ",", 1)
                out.append(nl)
        else:
            out.append(line)
    if not found:
        raise ValueError(f"name {old_name!r} not found in plant object")
    return "".join(out)


def _equipment_list(zone: str, labels: list[str]) -> str:
    lines = [
        "ZoneHVAC:EquipmentList,",
        f"  {zone} Equipment,                                !- Name",
        "  SequentialLoad,                                          !- Load Distribution Scheme",
    ]
    for i, label in enumerate(labels, start=1):
        last = i == len(labels)
        lines.append("  ZoneHVAC:WaterToAirHeatPump,                             !- Zone Equipment Object Type")
        lines.append(f"  {zone} WAHP {label},                          !- Zone Equipment Name")
        lines.append(f"  {i},                                                       !- Zone Equipment Cooling Sequence")
        lines.append(f"  {i},                                                       !- Zone Equipment Heating or No-Load Sequence")
        lines.append("  ,                                                        !- Zone Equipment Sequential Cooling Fraction Schedule Name")
        lines.append(("  ;" if last else "  ,") + "                                                        !- Zone Equipment Sequential Heating Fraction Schedule Name")
    return "\n".join(lines)


def _nodelist(name: str, nodes: list[str]) -> str:
    lines = ["NodeList,", f"  {name},                                            !- Name"]
    for i, node in enumerate(nodes):
        term = ";" if i == len(nodes) - 1 else ","
        lines.append(f"  {node}{term}")
    return "\n".join(lines)


def _require_totals(zone: str, totals: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if not totals.get(k)]
    if missing:
        raise ValueError(
            f"{zone} missing sizing totals {missing}; refuse independent Autosize clones"
        )


def expand_complete_banks(
    src: str,
    plan: dict[str, Any],
    *,
    sizing_totals: dict[str, dict[str, Any]],
) -> str:
    """Replace each zone W2A unit with complete labeled banks and plant references."""
    text = normalize_idf(src)
    by_zone = {row["eplus_zone"]: row for row in plan["zones"]}
    for z in NINE_ZONES:
        row = by_zone[z]
        labels = bank_labels(int(row["n_banks"]))
        fr = dict(row["fractions"])
        totals = sizing_totals[z]
        _require_totals(z, totals, "heating_capacity_w", "heating_airflow_m3s")
        h_caps = split_autosized_total(float(totals["heating_capacity_w"]), fr)
        h_airs = split_autosized_total(float(totals["heating_airflow_m3s"]), fr)
        c_air_total = float(totals.get("cooling_airflow_m3s") or totals["heating_airflow_m3s"])
        c_airs = split_autosized_total(c_air_total, fr)
        c_cap_total = totals.get("cooling_capacity_w")
        c_caps = split_autosized_total(float(c_cap_total), fr) if c_cap_total else None
        h_wtr_total = totals.get("heating_water_m3s")
        h_wtrs = split_autosized_total(float(h_wtr_total), fr) if h_wtr_total else None
        c_wtr_total = totals.get("cooling_water_m3s")
        c_wtrs = split_autosized_total(float(c_wtr_total), fr) if c_wtr_total else None

        specs = [
            (ZONEHVAC_TYPE, f"{z} WAHP"),
            (FAN_TYPE, f"{z} WAHP Supply Fan"),
            (OA_MIX_TYPE, f"{z} WAHP OA Mixing Box"),
            (HTG_TYPE, f"{z} WAHP Heating Coil"),
            (CLG_TYPE, f"{z} WAHP Cooling Coil"),
            (SUPP_TYPE, f"{z} WAHP Supp Heating Coil"),
            (OA_NODE_TYPE, f"{z} WAHP Outside Air Inlet"),
            (BRANCH_TYPE, f"{z} Heating Condenser Branch"),
            (BRANCH_TYPE, f"{z} Cooling Condenser Branch"),
        ]
        for obj_type, name in specs:
            parent = find_named_object(text, obj_type, name)
            if not parent:
                raise ValueError(f"missing {obj_type} {name}")
            clones = []
            for label in labels:
                cloned = _relabel_wahp_block(parent, z, label)
                if obj_type == BRANCH_TYPE:
                    cloned = cloned.replace(f"{z} Heating Condenser Branch", f"{z} Heating Condenser Branch {label}")
                    cloned = cloned.replace(f"{z} Cooling Condenser Branch", f"{z} Cooling Condenser Branch {label}")
                if obj_type == HTG_TYPE:
                    cloned = replace_comment_field(cloned, "Rated Heating Capacity", f"{h_caps[label]:.6g}")
                    cloned = replace_comment_field(cloned, "Rated Air Flow Rate", f"{h_airs[label]:.6g}")
                    if h_wtrs:
                        cloned = replace_comment_field(cloned, "Rated Water Flow Rate", f"{h_wtrs[label]:.6g}")
                if obj_type == CLG_TYPE:
                    cloned = replace_comment_field(cloned, "Rated Air Flow Rate", f"{c_airs[label]:.6g}")
                    if c_caps:
                        cloned = replace_comment_field(cloned, "Rated Total Cooling Capacity", f"{c_caps[label]:.6g}")
                    if c_wtrs:
                        cloned = replace_comment_field(cloned, "Rated Water Flow Rate", f"{c_wtrs[label]:.6g}")
                if obj_type == FAN_TYPE:
                    cloned = replace_comment_field(cloned, "Maximum Flow Rate", f"{h_airs[label]:.6g}")
                if obj_type == ZONEHVAC_TYPE:
                    cloned = replace_comment_field(cloned, "Heating Supply Air Flow Rate", f"{h_airs[label]:.6g}")
                    cloned = replace_comment_field(cloned, "Cooling Supply Air Flow Rate", f"{c_airs[label]:.6g}")
                    try:
                        cloned = replace_comment_field(
                            cloned, "No Load Supply Air Flow Rate", f"{h_airs[label]:.6g}"
                        )
                    except ValueError:
                        pass
                    try:
                        cloned = replace_comment_field(
                            cloned,
                            "Supply Air Flow Rate When No Cooling or Heating is Needed",
                            f"{h_airs[label]:.6g}",
                        )
                    except ValueError:
                        pass
                clones.append(cloned)
            text = _replace_block(text, parent, "\n\n".join(clones))

        el = find_named_object(text, EQUIP_LIST_TYPE, f"{z} Equipment")
        if not el:
            raise ValueError(f"missing equipment list for {z}")
        text = _replace_block(text, el, _equipment_list(z, labels))

        inlet_nodes = [f"{z} WAHP {label} Supply Inlet" for label in labels]
        return_nodes = [f"{z} WAHP {label} Return" for label in labels]
        n_in = _nodelist(f"{z} WAHP Supply Inlet List", inlet_nodes)
        n_ex = _nodelist(f"{z} WAHP Return List", return_nodes)
        conn = None
        for block in iter_objects(text, EQUIP_CONN_TYPE):
            if field_by_comment(block, "Zone Name") == z:
                conn = block
                break
        if not conn:
            raise ValueError(f"missing EquipmentConnections for {z}")
        conn2 = conn.replace(f"{z} WAHP Supply Inlet", f"{z} WAHP Supply Inlet List", 1)
        conn2 = conn2.replace(f"{z} WAHP Return", f"{z} WAHP Return List", 1)
        text = _replace_block(text, conn, conn2 + "\n\n" + n_in + "\n\n" + n_ex)

        h_names = [f"{z} Heating Condenser Branch {label}" for label in labels]
        c_names = [f"{z} Cooling Condenser Branch {label}" for label in labels]
        for obj_type in ("BranchList", "Connector:Splitter", "Connector:Mixer"):
            for block in iter_objects(text, obj_type):
                if f"{z} Heating Condenser Branch" in block or f"{z} Cooling Condenser Branch" in block:
                    updated = _expand_name_line(block, f"{z} Heating Condenser Branch", h_names)
                    updated = _expand_name_line(updated, f"{z} Cooling Condenser Branch", c_names)
                    text = _replace_block(text, block, updated)
    return text


def assert_reference_integrity(src: str, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fail if bank children reference deleted parents or Autosize every clone."""
    issues: list[str] = []
    htg = {field_by_comment(b, "Name"): b for b in iter_objects(src, HTG_TYPE)}
    clg = {field_by_comment(b, "Name"): b for b in iter_objects(src, CLG_TYPE)}
    fans = {field_by_comment(b, "Name"): b for b in iter_objects(src, FAN_TYPE)}
    zh = {field_by_comment(b, "Name"): b for b in iter_objects(src, ZONEHVAC_TYPE)}
    branches = {field_by_comment(b, "Name"): b for b in iter_objects(src, BRANCH_TYPE)}
    for name, block in zh.items():
        fan = field_by_comment(block, "Supply Air Fan Name")
        hc = field_by_comment(block, "Heating Coil Name")
        cc = field_by_comment(block, "Cooling Coil Name")
        if fan not in fans:
            issues.append(f"{name} fan {fan} missing")
        if hc not in htg:
            issues.append(f"{name} heating coil {hc} missing")
        if cc not in clg:
            issues.append(f"{name} cooling coil {cc} missing")
    for name, block in htg.items():
        cap = field_by_comment(block, "Rated Heating Capacity") or ""
        air = field_by_comment(block, "Rated Air Flow Rate") or ""
        if cap.lower() == "autosize" or air.lower() == "autosize":
            issues.append(f"{name} still Autosize (independent clone forbidden)")
        inlet = field_by_comment(block, "Water Inlet Node Name")
        outlet = field_by_comment(block, "Water Outlet Node Name")
        matched = [
            b
            for b in branches.values()
            if inlet and inlet in b and outlet and outlet in b
        ]
        if not matched:
            issues.append(f"{name} water nodes not on a plant branch")
    if plan:
        by_zone = {row["eplus_zone"]: row for row in plan["zones"]}
        for z, row in by_zone.items():
            labels = bank_labels(int(row["n_banks"]))
            for label in labels:
                nm = f"{z} WAHP {label} Heating Coil"
                if nm not in htg:
                    issues.append(f"missing bank coil {nm}")
                zh_name = f"{z} WAHP {label}"
                if zh_name not in zh:
                    issues.append(f"missing ZoneHVAC {zh_name}")
                br_h = f"{z} Heating Condenser Branch {label}"
                if br_h not in branches:
                    issues.append(f"missing plant branch {br_h}")
    if issues:
        raise ValueError("Track B reference integrity failed: " + "; ".join(issues[:12]))
    return {
        "ok": True,
        "n_heating_coils": len(htg),
        "n_zonehvac": len(zh),
        "n_fans": len(fans),
        "public_label": PUBLIC_LABEL,
    }


def scored_runtime_w2a_pass(gate: dict[str, Any]) -> bool:
    if gate.get("w2a_phase_fail_closed") or gate.get("w2a_phase_unparseable"):
        return False
    phase = gate.get("w2a_low_airflow_by_phase") or {}
    return (
        int(phase.get("scored_runtime") or 0) == 0
        and int(gate.get("severe_count") or 0) == 0
        and int(gate.get("fatal_count") or 0) == 0
    )


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
