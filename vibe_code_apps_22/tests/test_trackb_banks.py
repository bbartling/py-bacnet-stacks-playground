"""Track B capacity-class banks: six groups, multiple EquationFit objects, not 3-ton."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from eplus_gym.trackb_banks import (
    BAS_SIX_HP,
    PUBLIC_LABEL,
    assert_reference_integrity,
    champion_gates_template,
    clone_heating_coil_banks,
    expand_complete_banks,
    fractions_for,
    n_banks_for_hp_count,
    scored_runtime_w2a_pass,
    six_group_plan,
    split_autosized_total,
    structural_fixture_totals,
)
from eplus_gym.eplus_err import parse_eplus_err

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "scripts"))


def test_six_groups_use_67_hp_counts_not_3ton():
    plan = six_group_plan()
    assert plan["public_label"] == PUBLIC_LABEL
    assert plan["as_built"] is False
    assert plan["assumes_identical_3ton"] is False
    assert plan["hp_count_sum"] == 67
    assert len(plan["groups"]) == 6
    assert all(g["n_banks"] >= 2 for g in plan["groups"])
    assert all(g["tonnage_asserted"] is False for g in plan["groups"])
    dumped = json.dumps(plan)
    assert "identical 3-ton" not in dumped.lower()


def test_allocation_sensitivities_sum_to_one():
    for n in (2, 3):
        for sens in ("low", "base", "high"):
            frac = fractions_for(n, sensitivity=sens)
            assert pytest.approx(sum(frac.values()), rel=1e-9) == 1.0
    split = split_autosized_total(1000.0, {"small": 0.25, "medium": 0.5, "large": 0.25})
    assert split["medium"] == pytest.approx(500.0)
    with pytest.raises(ValueError):
        split_autosized_total(0.0, {"small": 1.0})


def test_clone_equationfit_banks_use_explicit_split_not_independent_autosize():
    block = (
        "Coil:Heating:WaterToAirHeatPump:EquationFit,\n"
        "  1F_Area_A WAHP Heating Coil,            !- Name\n"
        "  ,                                       !- Availability Schedule Name\n"
        "  Autosize,                               !- Rated Air Flow Rate {m3/s}\n"
        "  149430;                                 !- Rated Heating Capacity {W}\n"
    )
    clones = clone_heating_coil_banks(
        block, n_banks=3, zone="1F_Area_A", heating_total_w=1000.0, air_total_m3s=2.0
    )
    assert len(clones) == 3
    joined = "\n".join(clones)
    assert "149430" not in joined
    assert "Autosize" not in joined
    assert "1F_Area_A WAHP small Heating Coil" in joined
    assert "1F_Area_A WAHP large Heating Coil" in joined
    assert "500" in joined  # 0.5 * 1000
    split = split_autosized_total(1000.0, fractions_for(3))
    assert split["medium"] == pytest.approx(500.0)


def test_scored_runtime_w2a_gate_ignores_warmup_only_when_runtime_zero(tmp_path):
    err = tmp_path / "eplusout.err"
    err.write_text(
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 12 total times;\n"
        "*************  **   ~~~   **  during Warmup 12 times;\n"
        "*************  **   ~~~   **  during Sizing 0 times.\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n",
        encoding="utf-8",
    )
    gate = parse_eplus_err(err)
    assert gate["w2a_low_airflow_by_phase"]["warmup"] == 12
    assert gate["w2a_low_airflow_by_phase"]["scored_runtime"] == 0
    assert scored_runtime_w2a_pass(gate) is True
    gate["w2a_low_airflow_by_phase"]["scored_runtime"] = 1
    assert scored_runtime_w2a_pass(gate) is False


def test_eio_parser_extracts_heating_capacity():
    from eplus_gym.trackb_banks import parse_eio_component_sizing, sizing_totals_from_eio

    eio = (
        " Component Sizing Information, Coil:Heating:WaterToAirHeatPump:EquationFit, "
        "1F_Library_IMC WAHP Heating Coil, Design Size Rated Heating Capacity [W], 1000.0\n"
        " Component Sizing Information, Coil:Heating:WaterToAirHeatPump:EquationFit, "
        "1F_Library_IMC WAHP Heating Coil, Design Size Rated Air Flow Rate [m3/s], 0.5\n"
    )
    with pytest.raises(ValueError, match="missing heating"):
        sizing_totals_from_eio(eio)
    parsed = parse_eio_component_sizing(eio)
    assert parsed["1F_Library_IMC WAHP Heating Coil"]["heating_capacity_w"] == pytest.approx(1000.0)


def _ep26_uppercase_eio() -> str:
    """EnergyPlus 26.1 eio: UPPERCASE names + User-Specified heating capacity."""
    from eplus_native.idf_inspect import NINE_ZONES

    lines = [
        "! <Component Sizing Information>, Component Type, Component Name, Input Field Description, Value"
    ]
    for i, z in enumerate(NINE_ZONES):
        htg = f"{z.upper()} WAHP HEATING COIL"
        clg = f"{z.upper()} WAHP COOLING COIL"
        air = 1.0 + 0.1 * i
        lines.append(
            f" Component Sizing Information, COIL:HEATING:WATERTOAIRHEATPUMP:EQUATIONFIT, {htg}, "
            f"Design Size Rated Air Flow Rate [m3/s], {air}"
        )
        lines.append(
            f" Component Sizing Information, COIL:HEATING:WATERTOAIRHEATPUMP:EQUATIONFIT, {htg}, "
            f"User-Specified Rated Heating Capacity [W], 149430.00000"
        )
        lines.append(
            f" Component Sizing Information, COIL:COOLING:WATERTOAIRHEATPUMP:EQUATIONFIT, {clg}, "
            f"Design Size Rated Total Cooling Capacity [W], 20000.0"
        )
        lines.append(
            f" Component Sizing Information, COIL:COOLING:WATERTOAIRHEATPUMP:EQUATIONFIT, {clg}, "
            f"Design Size Rated Air Flow Rate [m3/s], {air}"
        )
    return "\n".join(lines) + "\n"


def test_eio_parser_matches_energyplus_26_uppercase_user_specified():
    from eplus_gym.trackb_banks import sizing_totals_from_eio

    totals = sizing_totals_from_eio(_ep26_uppercase_eio())
    lib = totals["1F_Library_IMC"]
    assert lib["heating_capacity_w"] == pytest.approx(149430.0)
    assert lib["heating_airflow_m3s"] == pytest.approx(1.0)
    assert lib["heating_capacity_source"] == "user_specified"
    assert lib["provenance"] == "live_energyplus_eio_component_sizing"
    assert totals["2F_Area_B"]["heating_airflow_m3s"] == pytest.approx(1.8)


def test_champion_gates_are_not_a_pass():
    gates = champion_gates_template()
    assert gates["long_campaign_allowed"] is False
    assert gates["champion"] is None
    assert gates["gates"]["heldout_after_selection"] == "locked_unseen"
    assert (APP / "contracts" / "trackb_archetype_v1.json").is_file()


def test_builder_refuses_a04_overwrite():
    from a04v2_build_trackb_banks import build_trackb_plan

    with pytest.raises(SystemExit, match="overwrite"):
        build_trackb_plan(sensitivity="base", run_id="lakeside_w2a_a04_dual_champion")


def test_trackb_expand_from_parent_creates_multiple_coils():
    from a04v2_build_trackb_banks import expand_autosize_banks
    from eplus_gym.idf_objects import iter_objects
    from eplus_gym.trackb_banks import HTG_TYPE, ZONEHVAC_TYPE, nine_zone_plan

    src = (APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf").read_text(
        encoding="utf-8", errors="replace"
    )
    n0 = len(iter_objects(src, HTG_TYPE))
    assert n0 == 9
    plan = nine_zone_plan()
    expanded = expand_autosize_banks(src, plan)
    n1 = len(iter_objects(expanded, HTG_TYPE))
    n_zh = len(iter_objects(expanded, ZONEHVAC_TYPE))
    assert n1 > 9
    assert n_zh == n1
    assert "149430" not in expanded
    integrity = assert_reference_integrity(expanded, plan)
    assert integrity["ok"] is True
    assert PUBLIC_LABEL in json.dumps(plan)


def test_trackb_expand_accepts_crlf_parent_bytes():
    """build_trackb_plan decodes A04 bytes (CRLF). Finder normalizes to LF."""
    from eplus_gym.idf_objects import iter_objects
    from eplus_gym.trackb_banks import (
        HTG_TYPE,
        expand_complete_banks,
        nine_zone_plan,
        structural_fixture_totals,
    )

    raw = (APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf").read_bytes()
    # GitHub checkout may LF-normalize; the expander must still accept CRLF parent bytes.
    if b"\r\n" not in raw:
        raw = raw.replace(b"\n", b"\r\n")
    assert b"\r\n" in raw
    src = raw.decode("utf-8", errors="replace")
    plan = nine_zone_plan()
    expanded = expand_complete_banks(src, plan, sizing_totals=structural_fixture_totals(src))
    assert len(iter_objects(expanded, HTG_TYPE)) > 9
    integrity = assert_reference_integrity(expanded, plan)
    assert integrity["ok"] is True


def test_rewrite_user_specified_heating_to_autosize_is_child_only():
    from eplus_gym.idf_objects import field_by_comment, find_named_object
    from eplus_gym.trackb_banks import HTG_TYPE, rewrite_parent_coils_to_autosize

    a04 = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    src = a04.read_text(encoding="utf-8", errors="replace")
    before = a04.read_bytes()
    child, meta = rewrite_parent_coils_to_autosize(src)
    assert meta["not_a04_overwrite"] is True
    assert meta["n_fields_rewritten"] > 0
    assert a04.read_bytes() == before
    coil = find_named_object(child, HTG_TYPE, "1F_Library_IMC WAHP Heating Coil")
    assert coil is not None
    assert str(field_by_comment(coil, "Rated Heating Capacity")).lower() == "autosize"


def test_rewrite_autosize_covers_cooling_fan_and_noload():
    from eplus_gym.idf_objects import field_by_comment, find_named_object
    from eplus_gym.trackb_banks import CLG_TYPE, FAN_TYPE, HTG_TYPE, ZONEHVAC_TYPE, rewrite_parent_coils_to_autosize

    a04 = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    src = a04.read_text(encoding="utf-8", errors="replace")
    child, meta = rewrite_parent_coils_to_autosize(src)
    assert meta["n_fields_rewritten"] > 9
    clg = find_named_object(child, CLG_TYPE, "1F_Library_IMC WAHP Cooling Coil")
    fan = find_named_object(child, FAN_TYPE, "1F_Library_IMC WAHP Supply Fan")
    zh = find_named_object(child, ZONEHVAC_TYPE, "1F_Library_IMC WAHP")
    assert clg is not None and fan is not None and zh is not None
    assert str(field_by_comment(clg, "Rated Air Flow Rate")).lower() == "autosize"
    assert str(field_by_comment(fan, "Maximum Flow Rate")).lower() == "autosize"

