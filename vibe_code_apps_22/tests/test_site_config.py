"""Site Config JSON + staged setpoint patches."""
from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym_app.site_config import (
    default_site_dsm_config,
    load_site_dsm_config,
    save_site_dsm_config,
    setpoints_summary,
    validate_setpoints_f,
)
from eplus_native.schedule_calendar_repair import apply_site_setpoints, _f_to_c


def test_site_config_round_trip(tmp_path: Path):
    cfg = default_site_dsm_config()
    cfg["setpoints_f"]["occupied_heating_f"] = 68.0
    cfg["peak_day_override"] = "2026-01-26"
    path = save_site_dsm_config(tmp_path, cfg)
    assert path.is_file()
    loaded = load_site_dsm_config(tmp_path)
    assert loaded["setpoints_f"]["occupied_heating_f"] == 68.0
    assert loaded["peak_day_override"] == "2026-01-26"
    assert "occ heat" in setpoints_summary(loaded)


def test_validate_setpoints_rejects_inverted():
    errs = validate_setpoints_f(
        {
            "occupied_heating_f": 76.0,
            "unoccupied_heating_f": 65.0,
            "occupied_cooling_f": 75.0,
            "unoccupied_cooling_f": 85.0,
        }
    )
    assert errs


def test_apply_site_setpoints_writes_htg_and_clg():
    stub = "Building,\n    X,\n    0.0;\n"
    out = apply_site_setpoints(
        stub,
        {
            "setpoints_f": {
                "occupied_heating_f": 70.0,
                "unoccupied_heating_f": 60.0,
                "occupied_cooling_f": 76.0,
                "unoccupied_cooling_f": 88.0,
            }
        },
    )
    assert "SCH_HtgSP" in out
    assert "SCH_ClgSP" in out
    assert f"{_f_to_c(70.0):.2f}" in out
    assert f"{_f_to_c(76.0):.2f}" in out
    assert f"{_f_to_c(60.0):.2f}" in out
    assert f"{_f_to_c(88.0):.2f}" in out


def test_stage_idf_applies_site_config(tmp_path: Path):
    from eplus_gym_app.dsm_console import stage_idf_for_period

    src = tmp_path / "champ.idf"
    src.write_text(
        "RunPeriod,\n    Annual,\n    1,1,2026,12,31,2026;\nBuilding,\n    X,\n    0;\n",
        encoding="utf-8",
    )
    save_site_dsm_config(
        tmp_path,
        {
            "setpoints_f": {
                "occupied_heating_f": 71.0,
                "unoccupied_heating_f": 62.0,
                "occupied_cooling_f": 74.0,
                "unoccupied_cooling_f": 86.0,
            }
        },
    )
    dest = tmp_path / "staged.idf"
    stage_idf_for_period(src, dest, "2026-01-26", "2026-01-26", site_root=tmp_path)
    text = dest.read_text(encoding="utf-8")
    assert "SCH_HtgSP" in text
    assert "SCH_ClgSP" in text
    assert src.read_text(encoding="utf-8").count("SCH_HtgSP") == 0
