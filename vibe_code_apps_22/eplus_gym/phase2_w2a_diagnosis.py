"""Phase 2: EnergyPlus W2A diagnosis (no model edits). Hypothesis until child confirms."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.idf_diagnostics import count_w2a_objects, model_capacity_card
from eplus_gym.idf_objects import field_by_comment, find_named_object, iter_objects, object_fields
from eplus_gym.phase2_mcp_evidence import (
    assert_mcp_evidence_complete,
    build_mcp_evidence_block,
    historical_err_evidence_from_phase1,
    sha256_text,
    stable_json,
)
from eplus_native.idf_inspect import NINE_ZONES

SCHEMA = "vibe22.mega.phase2_w2a_diagnosis.v2"
CONCLUSION_STRENGTH = "LEADING_ROOT_CAUSE_HYPOTHESIS"
HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"
CLG_TYPE = "Coil:Cooling:WaterToAirHeatPump:EquationFit"
ZONEHVAC_TYPE = "ZoneHVAC:WaterToAirHeatPump"
PLANT_LOOP_TYPE = "PlantLoop"
HP_COUNT_67 = {
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


def _num(raw: str | None) -> float | str | None:
    if raw is None or raw == "":
        return None
    low = raw.strip().lower()
    if low in {"autosize", "autocalculate"}:
        return low
    try:
        return float(raw)
    except ValueError:
        return raw


def _curve_domain(block: str) -> dict[str, Any]:
    mins: list[float] = []
    maxs: list[float] = []
    for line in block.splitlines():
        if "!-" not in line:
            continue
        label = line.split("!-")[-1].strip().lower()
        val_raw = line.split("!-")[0].strip().rstrip(",").strip()
        try:
            val = float(val_raw)
        except ValueError:
            continue
        if "minimum value" in label:
            mins.append(val)
        elif "maximum value" in label:
            maxs.append(val)
    return {
        "min_values": mins,
        "max_values": maxs,
        "wide_domain": any(abs(v) >= 50 for v in mins + maxs),
    }


def _unit_record(src: str, zone: str) -> dict[str, Any]:
    wahp_name = f"{zone} WAHP"
    wahp = find_named_object(src, ZONEHVAC_TYPE, wahp_name)
    htg = find_named_object(src, HTG_TYPE, f"{zone} WAHP Heating Coil")
    clg = find_named_object(src, CLG_TYPE, f"{zone} WAHP Cooling Coil")
    fan = find_named_object(src, "Fan:OnOff", f"{zone} WAHP Supply Fan")
    htg_cap_curve = field_by_comment(htg, "Heating Capacity Curve Name") if htg else None
    htg_cap_block = (
        find_named_object(src, "Curve:QuadLinear", htg_cap_curve) if htg_cap_curve else None
    )
    return {
        "zone": zone,
        "zonehvac_name": wahp_name,
        "hp_count_bas_split": HP_COUNT_67[zone],
        "operating_mode": "DrawThrough",
        "availability_schedule": field_by_comment(wahp, "Availability Schedule Name") if wahp else None,
        "fan_name": f"{zone} WAHP Supply Fan",
        "fan_max_flow_m3_s": _num(field_by_comment(fan, "Maximum Flow Rate") if fan else None),
        "heating_coil_name": f"{zone} WAHP Heating Coil",
        "cooling_coil_name": f"{zone} WAHP Cooling Coil",
        "rated_heating_capacity_w": _num(field_by_comment(htg, "Rated Heating Capacity") if htg else None),
        "rated_heating_cop": _num(field_by_comment(htg, "Rated Heating Coefficient of Performance") if htg else None),
        "rated_htg_airflow_m3_s": _num(field_by_comment(htg, "Rated Air Flow Rate") if htg else None),
        "rated_htg_waterflow_m3_s": _num(field_by_comment(htg, "Rated Water Flow Rate") if htg else None),
        "rated_cooling_capacity_w": _num(field_by_comment(clg, "Rated Total Cooling Capacity") if clg else None),
        "rated_cooling_cop": _num(field_by_comment(clg, "Rated Cooling Coefficient of Performance") if clg else None),
        "max_cycling_rate_per_hr": _num(field_by_comment(clg, "Maximum Cycling Rate") if clg else None),
        "htg_capacity_curve": htg_cap_curve,
        "htg_curve_domain": _curve_domain(htg_cap_block) if htg_cap_block else None,
        "plant_water_inlet": field_by_comment(htg, "Water Inlet Node Name") if htg else None,
        "plant_water_outlet": field_by_comment(htg, "Water Outlet Node Name") if htg else None,
    }


def _plant_loops(src: str) -> list[dict[str, Any]]:
    loops = []
    for block in iter_objects(src, PLANT_LOOP_TYPE):
        fields = object_fields(block)
        name = fields[1] if len(fields) > 1 else ""
        loops.append(
            {
                "name": name,
                "fluid_type": field_by_comment(block, "Fluid Type"),
                "max_loop_flow_rate": _num(field_by_comment(block, "Maximum Loop Flow Rate")),
                "demand_inlet_node": field_by_comment(block, "Plant Side Inlet Node Name"),
                "demand_outlet_node": field_by_comment(block, "Plant Side Outlet Node Name"),
            }
        )
    return loops


def build_w2a_diagnosis(
    *,
    idf_path: Path,
    mcp_load_result: Mapping[str, Any] | None = None,
    mcp_model_summary: Mapping[str, Any] | None = None,
    mcp_hvac_loops: Mapping[str, Any] | None = None,
    phase1_freeze: Mapping[str, Any] | None = None,
    require_mcp: bool = True,
) -> dict[str, Any]:
    src = idf_path.read_text(encoding="utf-8", errors="replace")
    idf_sha = hashlib.sha256(idf_path.read_bytes()).hexdigest()
    units = [_unit_record(src, z) for z in NINE_ZONES]
    caps = [u["rated_heating_capacity_w"] for u in units]
    identical_htg = all(c == 149430.0 for c in caps if isinstance(c, (int, float)))

    mcp_block = build_mcp_evidence_block(
        load_result=mcp_load_result,
        model_summary=mcp_model_summary,
        hvac_loops=mcp_hvac_loops,
    )
    if require_mcp:
        assert_mcp_evidence_complete(mcp_block)

    hypotheses = [
        {
            "id": "H1_identical_hardcoded_heating",
            "severity": "primary",
            "object_pattern": "Coil:Heating:WaterToAirHeatPump:EquationFit, * WAHP Heating Coil",
            "evidence": (
                "All nine heating coils hard-coded to 149430 W (87900×1.70 A04 dial) "
                "regardless of zone HP inventory (2–13 HP per zone)."
            ),
            "consequence": (
                "Giant-coil aggregation: one WAHP object represents many physical HPs "
                "with a single rated capacity."
            ),
        },
        {
            "id": "H2_autosized_airflow_vs_part_load",
            "severity": "primary",
            "object_pattern": "Rated Air Flow Rate = Autosize on all W2A coils and fans",
            "evidence": (
                "Rated airflow autosized against identical 149430 W capacity; historical ERR "
                "shows millions of recurring low-airflow prints at scored runtime (Phase 1 freeze)."
            ),
            "consequence": "Structural NO-GO for operational DSM until child-model confirms fix.",
            "forbidden_fix": "Do not shrink rated airflow alone to silence warnings.",
        },
        {
            "id": "H3_hp_count_contract_mismatch",
            "severity": "secondary",
            "object_pattern": "contracts/eplus_nine_to_six_zone_agg_v1.json default_hp_counts",
            "evidence": "BAS split sums to 67 HP; agg v1 sums to 79.",
            "consequence": "Child models must use 67-HP split ledger.",
        },
        {
            "id": "H4_equationfit_wide_curve_domain",
            "severity": "monitor",
            "object_pattern": "Curve:QuadLinear * HtgCapCurve",
            "evidence": "Performance curves allow wide w/x/y/z domains — extrapolation risk.",
            "consequence": "Verify cold-Monday operating points before promotion.",
        },
    ]

    err_evidence = historical_err_evidence_from_phase1(phase1_freeze)

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "diagnosed_at_utc": datetime.now(timezone.utc).isoformat(),
        "conclusion_strength": CONCLUSION_STRENGTH,
        "parent_idf": {
            "path_label": str(idf_path.name),
            "sha256": idf_sha,
            "immutable": True,
            "a04_champion": idf_path.name == A04_IDF_NAME,
        },
        "object_inventory": {
            **count_w2a_objects(src),
            **model_capacity_card(src),
            "n_plant_loops": len(iter_objects(src, PLANT_LOOP_TYPE)),
            "plant_loops": _plant_loops(src),
        },
        "units": units,
        "identical_hardcoded_heating_w": identical_htg,
        "hp_count_67_sum": sum(HP_COUNT_67.values()),
        "mcp_inspection": mcp_block,
        "historical_err_evidence": err_evidence,
        "leading_root_cause_hypotheses": hypotheses,
        "leading_root_cause_hypothesis_summary": (
            "LEADING_ROOT_CAUSE_HYPOTHESIS: identical 149430 W rated heating on all nine "
            "aggregated WAHP coils with autosized airflow likely drives chronic part-load "
            "airflow fraction below 25% of rated — pending live child-model confirmation."
        ),
        "model_edits_permitted": False,
        "bacnet_command_authority": 0,
        "vibe19_untouched": True,
    }
    body["diagnosis_sha256"] = sha256_text(
        stable_json({k: v for k, v in body.items() if k != "diagnosis_sha256"})
    )
    return body


def write_phase2_artifacts(
    diagnosis: dict[str, Any],
    *,
    json_out: Path,
    md_out: Path | None = None,
) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(diagnosis, indent=2) + "\n", encoding="utf-8")
    if md_out is None:
        return
    md_out.parent.mkdir(parents=True, exist_ok=True)
    mcp = diagnosis.get("mcp_inspection") or {}
    lines = [
        "# Vibe22 mega Phase 2 — W2A diagnosis (hypothesis)",
        "",
        f"**Conclusion strength:** `{diagnosis.get('conclusion_strength')}`",
        "",
        f"Machine-readable: [`{json_out.name}`](figures/vibe22_mega_phase2/{json_out.name})",
        "",
        "## Leading hypothesis",
        "",
        diagnosis.get("leading_root_cause_hypothesis_summary", ""),
        "",
        "## MCP tools invoked",
        "",
    ]
    for tool in mcp.get("mcp_tools_invoked") or []:
        h = (mcp.get("payload_sha256") or {}).get(tool, "")[:16]
        lines.append(f"- `{tool}` — payload SHA256 `{h}…`")
    lines.extend(["", "## Hypothesis ledger", ""])
    for h in diagnosis.get("leading_root_cause_hypotheses") or []:
        lines.append(f"### {h['id']} ({h['severity']})")
        lines.append(f"- **Objects:** `{h['object_pattern']}`")
        lines.append(f"- **Evidence:** {h['evidence']}")
        if h.get("forbidden_fix"):
            lines.append(f"- **Forbidden fix:** {h['forbidden_fix']}")
        lines.append("")
    lines.append("## Nine-zone unit table")
    lines.append("")
    lines.append("| Zone | ZoneHVAC | Heating coil | Rated htg W | Rated airflow | HP count |")
    lines.append("| --- | --- | --- | ---: | --- | ---: |")
    for u in diagnosis.get("units") or []:
        lines.append(
            f"| {u['zone']} | `{u['zonehvac_name']}` | `{u['heating_coil_name']}` | "
            f"{u['rated_heating_capacity_w']} | {u['rated_htg_airflow_m3_s']} | {u['hp_count_bas_split']} |"
        )
    lines.append("")
    lines.append(
        "*No model edits in Phase 2. Not a proven root cause until child-model runtime confirms. "
        "BACnet command authority = 0. Vibe19 untouched.*"
    )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
