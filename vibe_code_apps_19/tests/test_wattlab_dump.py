"""WattLab dump helpers — sensor stats slices and setpoint medians."""

from __future__ import annotations

import pandas as pd

from app.wattlab_dump import sensor_stats_tables, setpoints_table


def _frames_and_map():
    idx = pd.date_range("2024-03-04 08:00", periods=8, freq="1h", tz="UTC")  # Monday
    ahu = pd.DataFrame(
        {
            "discharge-air-temp": [55.0, 55.5, 56.0, 55.2, 70.0, 70.5, 71.0, 70.2],
            "duct-static-pressure": [1.5] * 4 + [0.1] * 4,
            "duct-static-pressure-sp": [1.5] * 8,
            "fan-status": [1, 1, 1, 1, 0, 0, 0, 0],
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    # No proof roles at all — appears only in the "all" slice
    meter = pd.DataFrame({"elec-power": [40.0] * 8}, index=idx)
    meter.attrs["equipment_type"] = "METER"
    frames = {"AHU_1": ahu, "METER_1": meter}
    role_map = {
        "AHU_1": {c: c for c in ahu.columns} | {"equipment_type": "AHU"},
        "METER_1": {"elec-power": "elec-power", "equipment_type": "METER"},
    }
    return frames, role_map


def test_sensor_stats_tables_slices_by_fan_proof():
    frames, role_map = _frames_and_map()
    tables = sensor_stats_tables(frames, role_map)
    assert set(tables) == {"all", "fan_on", "fan_off"}

    allt = tables["all"]
    assert {"equipment_id", "equipment_type", "role", "proof", "n", "mean", "p50"} <= set(allt.columns)
    # every mapped role present in "all"
    ahu_roles = set(allt.loc[allt["equipment_id"] == "AHU_1", "role"])
    assert "discharge-air-temp" in ahu_roles and "duct-static-pressure" in ahu_roles
    assert (allt["equipment_id"] == "METER_1").any()

    on = tables["fan_on"]
    off = tables["fan_off"]
    # fan-on slice: DAT mean ~55; fan-off ~70
    dat_on = on[(on["equipment_id"] == "AHU_1") & (on["role"] == "discharge-air-temp")]
    dat_off = off[(off["equipment_id"] == "AHU_1") & (off["role"] == "discharge-air-temp")]
    assert dat_on.iloc[0]["mean"] < 60 < dat_off.iloc[0]["mean"]
    assert dat_on.iloc[0]["n"] == 4 and dat_off.iloc[0]["n"] == 4
    # METER has no proof — excluded from on/off slices
    assert not (on["equipment_id"] == "METER_1").any()
    assert not (off["equipment_id"] == "METER_1").any()
    # proof column labels the mask source
    assert dat_on.iloc[0]["proof"] == "fan-status"


def test_setpoints_table_occupied_unoccupied_medians():
    idx = pd.date_range("2024-03-04 00:00", periods=24, freq="1h", tz="America/Chicago")
    # SP resets at night: 1.5 occupied (8-17), 0.5 otherwise
    sp_vals = [1.5 if 8 <= h < 18 else 0.5 for h in idx.hour]
    ahu = pd.DataFrame({"duct-static-pressure-sp": sp_vals}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": ahu}
    role_map = {"AHU_1": {"duct-static-pressure-sp": "duct-static-pressure-sp", "equipment_type": "AHU"}}

    df = setpoints_table(frames, role_map)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["role"] == "duct-static-pressure-sp"
    assert row["median_occupied"] is not None and row["median_unoccupied"] is not None
    assert row["median_occupied"] > row["median_unoccupied"]
    assert row["n_occupied"] + row["n_unoccupied"] == 24
