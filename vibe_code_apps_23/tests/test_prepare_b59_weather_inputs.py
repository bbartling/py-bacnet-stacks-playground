from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

SPEC = importlib.util.spec_from_file_location("b59_weather_prep", Path(__file__).parents[1] / "scripts/prepare_b59_weather_inputs.py")
prep = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prep)


def _response(times, *, tail=False):
    fields = {"surface_pressure": "hPa", "wind_speed_10m": "m/s", "wind_direction_10m": "°", "direct_normal_irradiance": "W/m²", "diffuse_radiation": "W/m²", "cloud_cover": "%", "precipitation": "mm"}
    if tail:
        fields |= {"temperature_2m": "°C", "dew_point_2m": "°C", "relative_humidity_2m": "%", "shortwave_radiation": "W/m²"}
    values = {"time": [stamp.strftime("%Y-%m-%dT%H:%M") for stamp in times]}
    defaults = {"surface_pressure": 1013.25, "wind_speed_10m": 2, "wind_direction_10m": 270, "direct_normal_irradiance": 300, "diffuse_radiation": 80, "cloud_cover": 50, "precipitation": 0, "temperature_2m": 15, "dew_point_2m": 8, "relative_humidity_2m": 60, "shortwave_radiation": 0}
    values |= {key: [defaults[key]] * len(times) for key in fields}
    return {"latitude": 37.85, "longitude": -122.21, "utc_offset_seconds": 0, "timezone": "GMT", "hourly_units": {"time": "iso8601", **fields}, "hourly": values}


def test_offline_prep_builds_strict_inputs_and_manifest(tmp_path):
    main = pd.date_range("2020-01-01", "2021-01-01", freq="h", inclusive="left", tz="UTC")
    tail = pd.date_range("2021-01-01", periods=8, freq="h", tz="UTC")
    aux_json, tail_json = tmp_path / "aux.json", tmp_path / "tail.json"
    aux_json.write_text(json.dumps(_response(main)))
    tail_json.write_text(json.dumps(_response(tail, tail=True)))
    manifest = prep.prepare(aux_json, tail_json, tmp_path / "out", aux_url="https://archive-api.open-meteo.com/v1/archive?x", tail_url="https://archive-api.open-meteo.com/v1/archive?tail", requested_coordinates=[37.87, -122.27])
    assert manifest["outputs"]["auxiliary_csv"]["rows"] == 8784
    assert manifest["outputs"]["measured_substitution_csv"]["rows"] == 8
    assert manifest["outputs"]["auxiliary_csv"]["columns"] == prep.AUX_COLUMNS
    assert manifest["sources"]["aux_2020"]["requested_coordinates"] == [37.87, -122.27]
    auxiliary = pd.read_csv(tmp_path / "out" / "b59_auxiliary_fixed_pst_2020.csv")
    assert auxiliary.iloc[0].pressure_pa == 101325
    assert auxiliary.iloc[0].total_sky_cover_tenths == 5
