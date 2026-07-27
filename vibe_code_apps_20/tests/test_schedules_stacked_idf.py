"""BUG-048/049: schedule patches on stacked + dial Liberty IDFs."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattlab.energyplus.patches.schedules import (
    apply_fan_avail_occupied_office,
    discover_operation_schedule_names,
)

ROOT = Path(__file__).resolve().parents[1]
R56 = Path("/data/runs/geo_b100_6stack_shape_r56_sched_mild/model.idf")
DIAL_R4 = Path("/data/uploads/prototypes/geo_b100_6fl_dial_r4.idf")


def test_discover_hvac_operation_on_dial_r4(tmp_path: Path) -> None:
    if not DIAL_R4.is_file():
        pytest.skip("dial_r4 IDF not mounted")
    text = DIAL_R4.read_text(encoding="utf-8", errors="replace")
    names = discover_operation_schedule_names(text)
    assert "HVACOperationSchd" in names


def test_occupied_office_patch_stacked_r56(tmp_path: Path) -> None:
    if not R56.is_file():
        pytest.skip("r56 twin not mounted")
    dest = tmp_path / "patched.idf"
    meta = apply_fan_avail_occupied_office(R56, dest)
    assert meta["ok"] is True
    assert "FanAvailSched" in meta["applied_schedules"]
    text = dest.read_text(encoding="utf-8")
    # Must not duplicate type-limits line (BUG-048 fatal)
    assert text.count("FanAvailSched, On/Off,") == 1
    assert "FanAvailSched, On/Off,\n    Fraction," not in text
    assert "Until: 7:00" in text or "Until: 7:00,0.0" in text


def test_occupied_office_patch_dial_r4(tmp_path: Path) -> None:
    if not DIAL_R4.is_file():
        pytest.skip("dial_r4 IDF not mounted")
    dest = tmp_path / "patched.idf"
    meta = apply_fan_avail_occupied_office(DIAL_R4, dest)
    assert meta["ok"] is True
    assert "HVACOperationSchd" in meta["applied_schedules"]
