"""Sizing inventory from EnergyPlus outputs + autosize freezing.

``parse_sizing_inventory`` extracts what it can from eplusout.eio and
eplustbl.csv text:

  - Zone Sizing Information rows (design loads + air flows per zone)
  - System Sizing Information rows (system air flow / capacity values)
  - Component Sizing Information rows (autosized field values per component)
  - Equipment Summary tables (Fans / Cooling Coils / Heating Coils /
    Central Plant) from eplustbl.csv when present

``freeze_autosized_values`` rewrites an IDF so autosized capacity/airflow
fields become fixed numbers taken from the inventory, optionally scaled by
per-category capacity factors (see
``wattlab.energyplus.patches.capacity.CAPACITY_FIELD_MAP``). Where an exact
IDF field has no direct simulated counterpart, the capacity engine uses
labeled surrogates (cooling-coil water flow for coil capacity, fan pressure
rise for fan power) and stamps the surrogate flags on the returned metadata.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from wattlab.energyplus.patches.capacity import (
    CAPACITY_FIELD_MAP,
    Resolver,
    scale_capacity_fields,
)

_TABLE_CAPTIONS = {
    "fans": "Fans",
    "cooling_coils": "Cooling Coils",
    "heating_coils": "Heating Coils",
    "central_plant": "Central Plant",
}


def _to_float(token: str) -> float | None:
    token = (token or "").strip().strip('"')
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _split_eio(line: str) -> list[str]:
    return [p.strip() for p in line.split(",")]


def _parse_eio(text: str) -> dict[str, list[dict[str, Any]]]:
    zones: list[dict[str, Any]] = []
    systems: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("!"):
            continue
        if line.startswith("Zone Sizing Information"):
            parts = _split_eio(line)
            if len(parts) >= 7:
                zones.append(
                    {
                        "zone": parts[1],
                        "load_type": parts[2],
                        "calc_design_load_w": _to_float(parts[3]),
                        "user_design_load_w": _to_float(parts[4]),
                        "calc_design_air_flow_m3s": _to_float(parts[5]),
                        "user_design_air_flow_m3s": _to_float(parts[6]),
                    }
                )
        elif line.startswith("System Sizing Information"):
            parts = _split_eio(line)
            if len(parts) < 4:
                continue
            entry: dict[str, Any] = {"system": parts[1]}
            if len(parts) >= 7 and _to_float(parts[4]) is not None:
                # E+ 9+ format: name, load type, peak kind, capacity,
                # calc air flow, user air flow, design day, peak time.
                entry.update(
                    {
                        "load_type": parts[2],
                        "peak_load_kind": parts[3],
                        "user_design_capacity_w": _to_float(parts[4]),
                        "calc_design_air_flow_m3s": _to_float(parts[5]),
                        "user_design_air_flow_m3s": _to_float(parts[6]),
                    }
                )
            else:
                # Legacy format: name, description, value.
                entry["description"] = parts[2]
                entry["value"] = _to_float(parts[3])
            systems.append(entry)
        elif line.startswith("Component Sizing Information"):
            parts = _split_eio(line)
            if len(parts) >= 5:
                components.append(
                    {
                        "object_type": parts[1],
                        "name": parts[2],
                        "description": parts[3],
                        "value": _to_float(parts[4]),
                    }
                )
    return {"zones": zones, "systems": systems, "components": components}


def _parse_tbl_tables(text: str) -> dict[str, list[dict[str, Any]]]:
    """Best-effort Equipment Summary style tables from eplustbl.csv text."""
    lines = text.splitlines()
    tables: dict[str, list[dict[str, Any]]] = {}
    caption_to_key = {v.upper(): k for k, v in _TABLE_CAPTIONS.items()}
    i = 0
    while i < len(lines):
        stripped = lines[i].strip().strip(",").strip()
        key = caption_to_key.get(stripped.upper())
        if key is None:
            i += 1
            continue
        # Next non-empty row starting with a comma is the header.
        j = i + 1
        header: list[str] | None = None
        while j < len(lines):
            row = lines[j]
            if row.strip():
                if row.startswith(","):
                    header = [c.strip() for c in row.split(",")]
                break
            j += 1
        if header is None:
            i = j + 1
            continue
        rows: list[dict[str, Any]] = []
        j += 1
        while j < len(lines):
            row = lines[j]
            if not row.strip() or not row.startswith(","):
                break
            cells = [c.strip() for c in row.split(",")]
            if len(cells) < 2 or not cells[1]:
                break
            entry: dict[str, Any] = {"name": cells[1]}
            for col, cell in zip(header[2:], cells[2:]):
                if not col:
                    continue
                value = _to_float(cell)
                entry[col] = cell if value is None else value
            rows.append(entry)
            j += 1
        tables[key] = rows
        i = j
    return tables


def parse_sizing_inventory(output_dir: Path) -> dict[str, Any]:
    """Structured sizing inventory from an EnergyPlus output directory."""
    output_dir = Path(output_dir)
    inventory: dict[str, Any] = {
        "zones": [],
        "systems": [],
        "components": [],
        "tables": {},
        "sources": [],
    }
    eio = output_dir / "eplusout.eio"
    if eio.is_file():
        parsed = _parse_eio(eio.read_text(encoding="utf-8", errors="replace"))
        inventory.update(parsed)
        inventory["sources"].append(str(eio))
    tbl = output_dir / "eplustbl.csv"
    if tbl.is_file():
        inventory["tables"] = _parse_tbl_tables(
            tbl.read_text(encoding="utf-8", errors="replace")
        )
        inventory["sources"].append(str(tbl))
    inventory["counts"] = {
        "zones": len(inventory["zones"]),
        "systems": len(inventory["systems"]),
        "components": len(inventory["components"]),
        "tables": {k: len(v) for k, v in inventory["tables"].items()},
    }
    return inventory


_UNITS_RE = re.compile(r"[\[{][^\]}]*[\]}]")


def _normalize_field(text: str) -> str:
    text = _UNITS_RE.sub("", text)
    for prefix in ("initial design size", "design size"):
        low = text.strip().lower()
        if low.startswith(prefix):
            text = text.strip()[len(prefix):]
            break
    return " ".join(text.split()).lower()


def inventory_resolver(inventory: Mapping[str, Any]) -> Resolver:
    """Resolver for the capacity engine: look up simulated design values.

    Matches Component Sizing Information rows by object type, object name
    (case-insensitive; EnergyPlus upper-cases names in outputs), and field
    description with units and "Design Size" prefixes stripped. Non-"Initial"
    rows win over "Initial Design Size" rows.
    """
    components = list(inventory.get("components") or [])

    def resolve(object_type: str, name: str, field_comment: str) -> float | None:
        want_field = _normalize_field(field_comment)
        want_type = object_type.strip().lower()
        want_name = name.strip().lower()
        best: float | None = None
        best_initial = True
        for comp in components:
            if str(comp.get("object_type", "")).strip().lower() != want_type:
                continue
            if str(comp.get("name", "")).strip().lower() != want_name:
                continue
            description = str(comp.get("description", ""))
            if _normalize_field(description) != want_field:
                continue
            value = comp.get("value")
            if value is None:
                continue
            is_initial = description.strip().lower().startswith("initial")
            if best is None or (best_initial and not is_initial):
                best = float(value)
                best_initial = is_initial
        return best

    return resolve


def freeze_autosized_values(
    idf_src: Path,
    idf_dest: Path,
    inventory: Mapping[str, Any],
    capacity_factors: Mapping[str, float] | None = None,
) -> dict:
    """Freeze autosized capacity/airflow fields to inventory values x factor.

    Categories not present in ``capacity_factors`` are frozen at 1.0 (the
    simulated design value). Fields whose design value cannot be resolved
    from the inventory stay autosized and are reported as unresolved.
    """
    factors: dict[str, float] = {category: 1.0 for category in CAPACITY_FIELD_MAP}
    for category, factor in (capacity_factors or {}).items():
        if category not in CAPACITY_FIELD_MAP:
            known = ", ".join(sorted(CAPACITY_FIELD_MAP))
            raise ValueError(f"Unknown capacity category {category!r}; known: {known}")
        factors[category] = float(factor)

    idf_src = Path(idf_src)
    idf_dest = Path(idf_dest)
    text = idf_src.read_text(encoding="utf-8", errors="replace")
    text, meta = scale_capacity_fields(
        text, factors, resolver=inventory_resolver(inventory)
    )
    header = "! WattLab sizing patch: freeze_autosized_values (conceptual sizing screen)\n"
    if "! WattLab sizing patch: freeze_autosized_values" not in text:
        text = header + text
    idf_dest.parent.mkdir(parents=True, exist_ok=True)
    idf_dest.write_text(text, encoding="utf-8")
    meta.update(
        {
            "patch": "freeze_autosized_values",
            "out": str(idf_dest),
            "ok": meta["autosize_frozen"] + meta["fields_scaled"] > 0,
        }
    )
    meta["flags"] = list(meta["flags"]) + [
        "conceptual_capacity_screen",
        "screening_only",
    ]
    return meta


# 1 refrigeration ton ≈ 3516.85 W; 1 mechanical hp ≈ 745.7 W
_TON_W = 3516.8528420667
_HP_W = 745.7


def _autosized_cooling_w(inventory: Mapping[str, Any]) -> float | None:
    """Best-effort total cooling plant capacity from sizing inventory (W)."""
    total = 0.0
    found = False
    for sys in inventory.get("systems") or []:
        load = str(sys.get("load_type") or "").lower()
        cap = sys.get("user_design_capacity_w")
        if cap is not None and ("cool" in load or "cooling" in load or not load):
            total += float(cap)
            found = True
    for comp in inventory.get("components") or []:
        desc = str(comp.get("description") or "").lower()
        otype = str(comp.get("object_type") or "").lower()
        val = comp.get("value")
        if val is None:
            continue
        if "chiller" in otype and ("nominal capacity" in desc or "capacity" in desc):
            total += float(val)
            found = True
        elif "cooling" in desc and "capacity" in desc and "coil" not in otype:
            total += float(val)
            found = True
    plant = (inventory.get("tables") or {}).get("central_plant") or []
    for row in plant:
        for key, val in row.items():
            if key == "name" or not isinstance(val, (int, float)):
                continue
            kl = key.lower()
            if "capacity" in kl or "nominal" in kl:
                total += float(val)
                found = True
    return total if found and total > 0 else None


def _autosized_fan_power_w(inventory: Mapping[str, Any]) -> float | None:
    fans = (inventory.get("tables") or {}).get("fans") or []
    total = 0.0
    found = False
    for row in fans:
        for key, val in row.items():
            if not isinstance(val, (int, float)):
                continue
            kl = key.lower()
            if "power" in kl or "rated electric" in kl:
                total += float(val)
                found = True
    for comp in inventory.get("components") or []:
        otype = str(comp.get("object_type") or "").lower()
        desc = str(comp.get("description") or "").lower()
        val = comp.get("value")
        if val is None:
            continue
        if "fan" in otype and ("power" in desc or "max power" in desc):
            total += float(val)
            found = True
    return total if found and total > 0 else None


def nameplate_to_capacity_factors(
    inventory: Mapping[str, Any],
    *,
    cooling_tons: float | None = None,
    fan_hp: float | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Map FM nameplate (tons / fan hp) → capacity_factors vs autosized inventory.

    Returns ``(factors, meta)``. Empty factors when inventory lacks comparable
    autosized values — caller should stamp NEEDS_INPUT / observe-only.
    """
    meta: dict[str, Any] = {
        "cooling_tons_nameplate": cooling_tons,
        "fan_hp_nameplate": fan_hp,
    }
    factors: dict[str, float] = {}
    if cooling_tons is not None and float(cooling_tons) > 0:
        auto_w = _autosized_cooling_w(inventory)
        meta["autosized_cooling_w"] = auto_w
        if auto_w and auto_w > 0:
            target_w = float(cooling_tons) * _TON_W
            factors["cooling_plant"] = target_w / auto_w
            factors["cooling_coils"] = factors["cooling_plant"]
            meta["cooling_factor"] = factors["cooling_plant"]
        else:
            meta["cooling_factor_error"] = "no_autosized_cooling_in_inventory"
    if fan_hp is not None and float(fan_hp) > 0:
        auto_w = _autosized_fan_power_w(inventory)
        meta["autosized_fan_w"] = auto_w
        if auto_w and auto_w > 0:
            target_w = float(fan_hp) * _HP_W
            ratio = target_w / auto_w
            factors["fan_power"] = ratio
            factors["fan_pressure"] = ratio
            meta["fan_factor"] = ratio
        else:
            # No fan power in inventory — leave note; do not invent.
            meta["fan_factor_error"] = "no_autosized_fan_power_in_inventory"
    return factors, meta
