from __future__ import annotations

import pandas as pd
import pytest

from vibe23.b59_weather import AUXILIARY_COLUMNS, B59WeatherError, build_2020_amy_epw


def _sources(tmp_path, *, bad_night=False, drop_measured=False, drop_tail=False):
    # Build exactly the UTC window that maps to fixed-PST calendar year 2020.
    local = pd.date_range("2020-01-01", "2021-01-01", freq="15min", inclusive="left", tz="Etc/GMT+8")
    utc = local.tz_convert("UTC")
    ghi = ((local.hour >= 10) & (local.hour <= 14)).astype(float) * 300
    if bad_night:
        ghi[0] = 100
    measured = pd.DataFrame({"date": utc, "air_temp_set_1": 15.0, "dew_point_temperature_set_1d": 8.0, "relative_humidity_set_1": 60.0, "solar_radiation_set_1": ghi})
    if drop_measured:
        measured = measured.drop(index=5)
    if drop_tail:
        # Match the published file: one start-of-hour record remains at 16:00
        # PST, which is not enough to form a measured hourly value.
        measured = measured.iloc[:-31]
    measured_path = tmp_path / "site_weather.csv"
    measured.to_csv(measured_path, index=False)
    hourly_utc = local[::4].tz_convert("UTC")
    auxiliary = pd.DataFrame({
        "timestamp_utc": hourly_utc, "pressure_pa": 101325.0, "wind_direction_deg": 270.0, "wind_speed_m_s": 2.0,
        "dni_w_m2": 400.0, "dhi_w_m2": 80.0, "precipitation_mm": 0.0, "total_sky_cover_tenths": 5.0, "opaque_sky_cover_tenths": 3.0,
    })
    assert tuple(auxiliary.columns) == AUXILIARY_COLUMNS
    aux_path = tmp_path / "aux.csv"
    auxiliary.to_csv(aux_path, index=False)
    return measured_path, aux_path


def test_builds_hash_bearing_leap_year_epw(tmp_path):
    measured, auxiliary = _sources(tmp_path)
    output = tmp_path / "out" / "b59_2020.epw"
    manifest = build_2020_amy_epw(measured, auxiliary, output, latitude_deg=37.87, longitude_deg=-122.27, elevation_m=50, auxiliary_provenance={"provider": "Open-Meteo", "source_url": "https://archive-api.open-meteo.com/", "requested_coordinates": [37.87, -122.27], "returned_coordinates": [37.84, -122.24]})
    lines = output.read_text().splitlines()
    assert len(lines) == 8 + 8784
    assert manifest["output_epw"]["hourly_rows"] == 8784
    assert manifest["measured_source"]["raw_timestamp_timezone"] == "UTC"
    assert manifest["auxiliary_source"]["provenance"]["returned_coordinates"] == [37.84, -122.24]
    assert lines[8].split(",")[3:5] == ["1", "60"]
    assert lines[4] == "HOLIDAYS/DAYLIGHT SAVINGS,Yes,0,0,0"


@pytest.mark.parametrize("kwargs, match", [({"bad_night": True}, "civil night"), ({"drop_measured": True}, "gaps")])
def test_rejects_nonphysical_solar_or_gap(tmp_path, kwargs, match):
    measured, auxiliary = _sources(tmp_path, **kwargs)
    with pytest.raises(B59WeatherError, match=match):
        build_2020_amy_epw(measured, auxiliary, tmp_path / "bad.epw", latitude_deg=37.87, longitude_deg=-122.27, elevation_m=50)


def test_missing_tail_requires_explicit_hashed_substitution(tmp_path):
    measured, auxiliary = _sources(tmp_path, drop_tail=True)
    with pytest.raises(B59WeatherError, match="coverage is incomplete"):
        build_2020_amy_epw(measured, auxiliary, tmp_path / "bad.epw", latitude_deg=37.87, longitude_deg=-122.27, elevation_m=50)
    local = pd.date_range("2020-12-31 16:00", "2021-01-01", freq="h", inclusive="left", tz="Etc/GMT+8")
    substitute = pd.DataFrame({"timestamp_utc": local.tz_convert("UTC"), "dry_bulb_c": 15.0, "dew_point_c": 8.0, "relative_humidity_pct": 60.0, "ghi_w_m2": 0.0})
    substitute_path = tmp_path / "measured_tail_substitution.csv"
    substitute.to_csv(substitute_path, index=False)
    manifest = build_2020_amy_epw(measured, auxiliary, tmp_path / "hybrid.epw", latitude_deg=37.87, longitude_deg=-122.27, elevation_m=50, measured_substitution_path=substitute_path)
    disclosure = manifest["measured_source"]["coverage"]["substitution"]
    assert len(disclosure["hours"]) == 8
    assert disclosure["sha256"]
