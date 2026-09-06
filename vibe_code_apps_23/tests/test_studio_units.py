"""Unit conversion helpers for Studio display."""
from vibe23.studio.units import (
    display_area,
    display_temp,
    energy_intensity,
    f_to_c,
    normalize_units,
    temp_unit,
)


def test_normalize_and_temp_area():
    assert normalize_units("metric") == "metric"
    assert normalize_units("si") == "metric"
    assert normalize_units(None) == "imperial"
    assert abs(f_to_c(32.0) - 0.0) < 1e-9
    assert abs(display_temp(32.0, "metric") - 0.0) < 1e-9
    assert abs(display_temp(72.0, "imperial") - 72.0) < 1e-9
    assert abs(display_area(10.76391041671, "metric") - 1.0) < 1e-6
    assert temp_unit("metric") == "°C"
    assert abs(energy_intensity(10.0, floor_ft2=10.76391041671, units="metric") - 10.0) < 1e-6


def test_packaged_idf_and_epw_resolve():
    from vibe23.residential.model import DEFAULT_EPW, MODEL_IDF, find_denver_epw

    assert MODEL_IDF.is_file()
    assert DEFAULT_EPW.is_file()
    found = find_denver_epw()
    assert found is not None
    assert found.resolve() == DEFAULT_EPW.resolve()
