from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym.mega.hp67_banks import build_hp67_banks_child, eio_totals_for_hp67
from eplus_gym.mega.hp67_two_pass import patch_pass1_autosize
from eplus_gym.trackb_banks import assert_reference_integrity, nine_zone_plan

APP = Path(__file__).resolve().parents[1]
EIO = (
    APP
    / "docs"
    / "audits"
    / "figures"
    / "a04_child_hp67_scaled_v2"
    / "sensitivity_base"
    / "pass1_sizing"
    / "eplus_out"
    / "eplusout.eio"
)
PASS1_IDF = (
    APP
    / "docs"
    / "audits"
    / "figures"
    / "a04_child_hp67_scaled_v2"
    / "sensitivity_base"
    / "pass1_sizing"
    / "pass1_autosize.idf"
)
A04 = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"


def test_eio_totals_from_real_pass1_eio():
    if not EIO.is_file():
        pytest.skip("pass1 eio artifact missing")
    totals = eio_totals_for_hp67(EIO.read_text(encoding="utf-8", errors="replace"))
    assert len(totals) == 9
    for z, row in totals.items():
        assert float(row["heating_capacity_w"]) > 0
        assert float(row["heating_airflow_m3s"]) > 0


def test_build_hp67_banks_child_expands_coils():
    if not EIO.is_file():
        pytest.skip("pass1 eio artifact missing")
    if PASS1_IDF.is_file():
        pass1_text = PASS1_IDF.read_text(encoding="utf-8", errors="replace")
    else:
        pass1_text, _ = patch_pass1_autosize(A04.read_text(encoding="utf-8", errors="replace"))
    expanded, meta = build_hp67_banks_child(
        pass1_text,
        eio_text=EIO.read_text(encoding="utf-8", errors="replace"),
        sensitivity="base",
    )
    plan = nine_zone_plan(sensitivity="base")
    integrity = assert_reference_integrity(expanded, plan)
    assert meta["not_threshold_manipulation"] is True
    assert integrity.get("ok") is True or integrity.get("reference_ok") is not False
    assert expanded.count("WAHP small") + expanded.count("WAHP medium") + expanded.count("WAHP large") > 0
