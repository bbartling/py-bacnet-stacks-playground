"""Track B capacity-class banks: six groups, multiple EquationFit objects, not 3-ton."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from eplus_gym.trackb_banks import (
    BAS_SIX_HP,
    PUBLIC_LABEL,
    champion_gates_template,
    clone_heating_coil_banks,
    fractions_for,
    n_banks_for_hp_count,
    scored_runtime_w2a_pass,
    six_group_plan,
    split_autosized_total,
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


def test_clone_equationfit_banks_are_autosized_not_one_giant_coil():
    block = (
        "Coil:Heating:WaterToAirHeatPump:EquationFit,\n"
        "  1F_Area_A WAHP Heating Coil,            !- Name\n"
        "  ,                                       !- Availability Schedule Name\n"
        "  Autosize,                               !- Rated Air Flow Rate {m3/s}\n"
        "  149430;                                 !- Rated Heating Capacity {W}\n"
    )
    clones = clone_heating_coil_banks(block, n_banks=3, zone="1F_Area_A")
    assert len(clones) == 3
    joined = "\n".join(clones)
    assert "149430" not in joined
    assert joined.count("Autosize") >= 6
    assert "1F_Area_A WAHP Heating Coil small" in joined
    assert "1F_Area_A WAHP Heating Coil large" in joined


def test_scored_runtime_w2a_gate_ignores_warmup_only_when_runtime_zero(tmp_path):
    err = tmp_path / "eplusout.err"
    err.write_text(
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **   During Warmup, This error occurred 12 total times;\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors\n",
        encoding="utf-8",
    )
    gate = parse_eplus_err(err)
    assert gate["w2a_low_airflow_by_phase"]["warmup"] == 12
    assert gate["w2a_low_airflow_by_phase"]["scored_runtime"] == 0
    assert scored_runtime_w2a_pass(gate) is True
    gate["w2a_low_airflow_by_phase"]["scored_runtime"] = 1
    assert scored_runtime_w2a_pass(gate) is False


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
    from eplus_gym.trackb_banks import HTG_TYPE, nine_zone_plan

    src = (APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf").read_text(
        encoding="utf-8", errors="replace"
    )
    n0 = len(iter_objects(src, HTG_TYPE))
    assert n0 == 9
    expanded = expand_autosize_banks(src, nine_zone_plan())
    n1 = len(iter_objects(expanded, HTG_TYPE))
    assert n1 > 9
    assert "149430" not in expanded or expanded.lower().count("autosize") >= n1
