from __future__ import annotations

import json
from pathlib import Path

EXPECTED_FILES = {
    "ashp_cw.csv",
    "ashp_hw.csv",
    "ashp_meter.csv",
    "ele.csv",
    "hp_hws_temp.csv",
    "occ.csv",
    "rtu_econ_sp.csv",
    "rtu_fan_spd.csv",
    "rtu_ma_t.csv",
    "rtu_oa_damper.csv",
    "rtu_oa_fr.csv",
    "rtu_oa_t.csv",
    "rtu_plenum_p.csv",
    "rtu_ra_t.csv",
    "rtu_sa_fr.csv",
    "rtu_sa_p_sp.csv",
    "rtu_sa_t.csv",
    "rtu_sa_t_sp.csv",
    "site_weather.csv",
    "uft_fan_spd.csv",
    "uft_hw_valve.csv",
    "wifi.csv",
    "zone_co2.csv",
    "zone_temp_exterior.csv",
    "zone_temp_interior.csv",
    "zone_temp_sp_c.csv",
    "zone_temp_sp_h.csv",
}


def test_all_27_cleaned_files_have_one_fail_closed_role():
    path = Path(__file__).parents[1] / "config" / "b59_model_data_roles.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    files = config["files"]
    assert len(files) == 27
    assert {item["file"] for item in files} == EXPECTED_FILES
    assert len({item["sha256"] for item in files}) == 27
    assert all(item["model_use_category"] and item["do_not_use"] for item in files)
    assert "no ASHRAE 90.1-2015 edition" in config["model_policy"]["code_basis_correction"]
