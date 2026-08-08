"""Post-ExpandObjects W2A / plant field mutator (live knobs only).

Every knob must change a concrete expanded IDF object field. Dead IdealLoads /
pre-expand capacity levers are refused.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, fields
from typing import Any

# Baseline when Rated Heating Capacity is autosize (≈2.7 MMBtu/h / 9 zones).
DEFAULT_HTG_COIL_CAPACITY_W = 87_900.0
# Baseline when Rated Power is autosize — derived from head via affinity-ish placeholder.
DEFAULT_PUMP_POWER_W = 2_500.0

DEAD_KNOBS = frozenset(
    {
        "heating_capacity_mmbtu_h",
        "oa_occupied_frac",
        "cap",
        "IdealLoads",
        "ideal_loads_capacity",
    }
)

LIVE_KNOB_NAMES = frozenset(
    {
        "htg_coil_capacity_mult",
        "htg_coil_cop_mult",
        "fan_delta_p_mult",
        "fan_eff_mult",
        "pump_power_mult",
        "loop_setpoint_c",
        "oa_frac_scale",
        "optimum_start_h",
    }
)


@dataclass(frozen=True)
class W2APlantKnobs:
    htg_coil_capacity_mult: float = 1.0
    htg_coil_cop_mult: float = 1.0
    fan_delta_p_mult: float = 1.0
    fan_eff_mult: float = 1.0
    pump_power_mult: float = 1.0
    loop_setpoint_c: float | None = None  # None → leave HVACTemplate-Always 34
    oa_frac_scale: float = 1.0
    optimum_start_h: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def refuse_dead_knobs(knobs: dict[str, Any]) -> None:
    bad = sorted(set(knobs) & DEAD_KNOBS)
    unknown = sorted(set(knobs) - LIVE_KNOB_NAMES - {"trial_id", "label"})
    if bad:
        raise ValueError(f"dead W2A knobs refused (do not affect expanded plant): {bad}")
    if unknown:
        raise ValueError(f"unknown W2A knobs: {unknown}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _replace_field_by_comment(
    block: str,
    *,
    comment_substr: str,
    new_value: str,
    object_type: str,
    object_name: str,
    ledger: list[dict[str, Any]],
) -> str:
    lines = block.splitlines(keepends=True)
    out: list[str] = []
    changed = False
    for line in lines:
        if (not changed) and comment_substr.lower() in line.lower() and "!" in line:
            m = re.match(r"^(\s*)([^,;]+)([,;])(.*)$", line)
            if m:
                old = m.group(2).strip()
                if old != new_value:
                    ledger.append(
                        {
                            "object_type": object_type,
                            "object_name": object_name,
                            "field_comment": comment_substr,
                            "old": old,
                            "new": new_value,
                        }
                    )
                    line = f"{m.group(1)}{new_value}{m.group(3)}{m.group(4)}\n" if line.endswith("\n") else f"{m.group(1)}{new_value}{m.group(3)}{m.group(4)}"
                    if not line.endswith("\n") and block.endswith("\n"):
                        line += "\n"
                changed = True
        out.append(line)
    return "".join(out)


def _object_name(block: str) -> str:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        return ""
    # second field is Name
    m = re.match(r"^\s*([^,;]+)", lines[1])
    return m.group(1).strip() if m else ""


def _iter_objects(text: str, object_type: str) -> list[tuple[int, int, str]]:
    """Return (start, end, block) spans for objects of the given type."""
    pat = re.compile(rf"(?mi)^({re.escape(object_type)})\s*,.*?;", re.S)
    return [(m.start(), m.end(), m.group(0)) for m in pat.finditer(text)]


def _scale_or_set_numeric(old: str, mult: float, *, autosize_baseline: float) -> str:
    s = old.strip()
    if s.lower() == "autosize" or s == "":
        return f"{autosize_baseline * mult:.6g}"
    try:
        return f"{float(s) * mult:.6g}"
    except ValueError:
        return f"{autosize_baseline * mult:.6g}"


def _mutate_coils(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    spans = _iter_objects(text, "Coil:Heating:WaterToAirHeatPump:EquationFit")
    if not spans:
        return text
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        # Always materialize capacity so autosize→numeric is a live change even at mult=1.
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Heating Capacity.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            new_v = _scale_or_set_numeric(
                old if old.lower() != "autosize" else "autosize",
                knobs.htg_coil_capacity_mult,
                autosize_baseline=DEFAULT_HTG_COIL_CAPACITY_W,
            )
            # When old was numeric, scale from that; when autosize, baseline*mult
            if old.lower() != "autosize":
                try:
                    new_v = f"{float(old) * knobs.htg_coil_capacity_mult:.6g}"
                except ValueError:
                    pass
            else:
                new_v = f"{DEFAULT_HTG_COIL_CAPACITY_W * knobs.htg_coil_capacity_mult:.6g}"
            if old != new_v:
                ledger.append(
                    {
                        "object_type": "Coil:Heating:WaterToAirHeatPump:EquationFit",
                        "object_name": name,
                        "field_comment": "Rated Heating Capacity",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        if knobs.htg_coil_cop_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Heating Coefficient of Performance.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{float(old) * knobs.htg_coil_cop_mult:.6g}"
                except ValueError:
                    new_v = f"{4.2 * knobs.htg_coil_cop_mult:.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Coil:Heating:WaterToAirHeatPump:EquationFit",
                            "object_name": name,
                            "field_comment": "Rated Heating COP",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_fans(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.fan_delta_p_mult == 1.0 and knobs.fan_eff_mult == 1.0:
        return text
    spans = _iter_objects(text, "Fan:OnOff")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        if knobs.fan_eff_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Fan Efficiency.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{min(0.95, float(old) * knobs.fan_eff_mult):.6g}"
                except ValueError:
                    new_v = f"{min(0.95, 0.7 * knobs.fan_eff_mult):.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Fan:OnOff",
                            "object_name": name,
                            "field_comment": "Fan Efficiency",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        if knobs.fan_delta_p_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Pressure Rise.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{float(old) * knobs.fan_delta_p_mult:.6g}"
                except ValueError:
                    new_v = f"{75.0 * knobs.fan_delta_p_mult:.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Fan:OnOff",
                            "object_name": name,
                            "field_comment": "Pressure Rise",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_pumps(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Scale Rated Pump Head only; leave Rated Power as autosize so E+ efficiency stays physical."""
    if knobs.pump_power_mult == 1.0:
        return text
    spans = _iter_objects(text, "Pump:ConstantSpeed")
    if not spans:
        spans = _iter_objects(text, "Pump:VariableSpeed")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        obj_type = block.split(",", 1)[0].strip()
        new_block = block
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Pump Head.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            try:
                new_v = f"{float(old) * knobs.pump_power_mult:.6g}"
            except ValueError:
                new_v = old
            if old != new_v:
                ledger.append(
                    {
                        "object_type": obj_type,
                        "object_name": name,
                        "field_comment": "Rated Pump Head",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_loop_setpoint(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.loop_setpoint_c is None:
        return text
    target = f"{float(knobs.loop_setpoint_c):.6g}"
    # HVACTemplate-Always 34 is the mixed-loop high setpoint schedule
    pat = re.compile(
        r"(?mi)^(Schedule:Compact,\s*\n\s*HVACTemplate-Always 34\s*,.*?;)",
        re.S,
    )
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    name = "HVACTemplate-Always 34"
    # Replace numeric Until values that are the constant 34
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)(34(?:\.0+)?)([,;])(.*)$", line)
        if mm and "Through" not in line and "For" not in line and "Until" not in line:
            old = mm.group(2)
            if old != target:
                ledger.append(
                    {
                        "object_type": "Schedule:Compact",
                        "object_name": name,
                        "field_comment": "loop high setpoint value",
                        "old": old,
                        "new": target,
                    }
                )
                line = f"{mm.group(1)}{target}{mm.group(3)}{mm.group(4)}"
                if not line.endswith("\n"):
                    line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _mutate_oa_frac(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.oa_frac_scale == 1.0:
        return text
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_OA\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)([0-9]*\.?[0-9]+)([,;])(.*)$", line)
        if mm and "Through" not in line and "For" not in line and "Until" not in line:
            old = mm.group(2)
            try:
                val = float(old)
            except ValueError:
                new_lines.append(line)
                continue
            if val > 0.0:
                new_v = f"{min(1.0, val * knobs.oa_frac_scale):.6g}"
                if new_v != old:
                    ledger.append(
                        {
                            "object_type": "Schedule:Compact",
                            "object_name": "SCH_OA",
                            "field_comment": "occupied OA fraction",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    line = f"{mm.group(1)}{new_v}{mm.group(3)}{mm.group(4)}"
                    if not line.endswith("\n"):
                        line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _snap_15min(hours: float) -> float:
    """Snap decimal hours to 15-min legal EnergyPlus Until times."""
    total_min = int(round(hours * 60.0 / 15.0) * 15)
    return total_min / 60.0


def _fmt_until(hours: float) -> str:
    h = int(math.floor(hours)) % 24
    m = int(round((hours - math.floor(hours)) * 60.0))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    if h == 0 and m == 0 and hours >= 24:
        return "24:00"
    if hours >= 24.0 - 1e-9:
        return "24:00"
    return f"{h:02d}:{m:02d}"


def _mutate_optimum_start(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if not knobs.optimum_start_h or abs(knobs.optimum_start_h) < 1e-9:
        return text
    advance = _snap_15min(float(knobs.optimum_start_h))
    if advance <= 0:
        return text
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_HtgSP\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    # Shift weekday morning Until times earlier by advance (15-min legal)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.search(r"Until:\s*(\d{1,2}):(\d{2})", line, re.I)
        if mm:
            hh, mi = int(mm.group(1)), int(mm.group(2))
            if hh == 24:
                hours = 24.0
            else:
                hours = hh + mi / 60.0
            # Morning band only: 05:00–08:00 → pull earlier for optimum start
            if 5.0 <= hours <= 8.0:
                new_h = max(0.0, hours - advance)
                new_h = _snap_15min(new_h)
                old_s = mm.group(0)
                new_s = f"Until: {_fmt_until(new_h)}"
                if old_s != new_s:
                    ledger.append(
                        {
                            "object_type": "Schedule:Compact",
                            "object_name": "SCH_HtgSP",
                            "field_comment": "optimum_start Until shift",
                            "old": old_s,
                            "new": new_s,
                        }
                    )
                    line = line.replace(old_s, new_s, 1)
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def apply_w2a_plant_knobs(expanded_idf_text: str, knobs: W2APlantKnobs | dict[str, Any]) -> dict[str, Any]:
    """Mutate expanded IDF text; return text, sha256, fields_changed, knobs."""
    if isinstance(knobs, dict):
        refuse_dead_knobs(knobs)
        known = {f.name for f in fields(W2APlantKnobs)}
        knobs = W2APlantKnobs(**{k: v for k, v in knobs.items() if k in known})
    text = expanded_idf_text
    ledger: list[dict[str, Any]] = []
    text = _mutate_coils(text, knobs, ledger)
    text = _mutate_fans(text, knobs, ledger)
    text = _mutate_pumps(text, knobs, ledger)
    text = _mutate_loop_setpoint(text, knobs, ledger)
    text = _mutate_oa_frac(text, knobs, ledger)
    text = _mutate_optimum_start(text, knobs, ledger)
    return {
        "text": text,
        "expanded_idf_sha256": sha256_text(text),
        "fields_changed": ledger,
        "knobs": knobs.as_dict(),
        "n_fields_changed": len(ledger),
    }


def detect_duplicate_models(
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail-closed uniqueness: different knobs must not share expanded SHA / empty ledger."""
    by_sha: dict[str, list[str]] = {}
    collisions: list[dict[str, Any]] = []
    empty_ledger: list[str] = []
    for t in trials:
        tid = str(t.get("trial_id") or t.get("id") or "?")
        sha = t.get("expanded_idf_sha256")
        fields_changed = t.get("fields_changed") or []
        if not fields_changed:
            empty_ledger.append(tid)
        if sha:
            by_sha.setdefault(str(sha), []).append(tid)
    for sha, ids in by_sha.items():
        if len(ids) > 1:
            # Only a collision if knobs differ
            knob_sets = []
            for t in trials:
                if str(t.get("trial_id") or t.get("id")) in ids:
                    knob_sets.append(t.get("knobs"))
            if len({json_dumps_stable(k) for k in knob_sets}) > 1:
                collisions.append({"expanded_idf_sha256": sha, "trial_ids": ids})
    unique = len(by_sha)
    fail = bool(collisions) or bool(empty_ledger)
    return {
        "attempted_runs": len(trials),
        "unique_models": unique,
        "duplicate_collisions": collisions,
        "empty_fields_changed": empty_ledger,
        "uniqueness_ok": not fail,
        "fail_closed": fail,
    }


def json_dumps_stable(obj: Any) -> str:
    import json

    return json.dumps(obj, sort_keys=True, default=str)


def plant_plausibility_check(expanded_idf_text: str) -> dict[str, Any]:
    """Expanded IDF must contain W2A coils + loop pump; no IdealLoads; strip cap 0."""
    t = expanded_idf_text
    has_coil = bool(re.search(r"(?mi)^Coil:Heating:WaterToAirHeatPump:EquationFit\s*,", t))
    has_pump = bool(re.search(r"(?mi)^Pump:(ConstantSpeed|VariableSpeed)\s*,", t))
    has_ideal = bool(re.search(r"(?mi)^ZoneHVAC:IdealLoadsAirSystem\s*,", t))
    # Supplemental strip capacity should remain 0 where present
    strip_ok = True
    for m in re.finditer(r"(?im)^(\s*)([^,;]+)([,;])(.*Supplemental Heating Coil Capacity.*)$", t):
        if m.group(2).strip() not in ("0", "0.0"):
            strip_ok = False
            break
    has_ewt = "Rated Entering Water Temperature" in t or "Entering Water" in t
    ok = has_coil and has_pump and (not has_ideal) and strip_ok
    return {
        "ok": ok,
        "has_w2a_heating_coil": has_coil,
        "has_loop_pump": has_pump,
        "has_ideal_loads": has_ideal,
        "supplemental_strip_capacity_zero": strip_ok,
        "ewt_or_loop_objects_present": has_ewt,
    }
