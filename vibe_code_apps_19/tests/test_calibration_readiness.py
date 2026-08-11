from __future__ import annotations

import pandas as pd

from app.calibration_readiness import FUEL_PACKAGE_NOTE, build_calibration_readiness


def test_calibration_readiness_labels_missing_fuel_and_utc():
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    frames = {"AHU_1": pd.DataFrame({"fan-status": [1] * 48}, index=idx)}
    seed = {
        "city": None,
        "lat": None,
        "lon": None,
        "floor_area_ft2": None,
        "building_type": None,
        "schedule_hints": {},
        "data_window": {"timezone": "UTC"},
    }
    doc = build_calibration_readiness(seed=seed, frames=frames, timezone="UTC")
    assert doc["model_seed_is_calibrated_model"] is False
    assert doc["ready"] is False
    assert "fuel_utility_data" in doc["missing_requirements"]
    assert "local_standard_timezone" in doc["missing_requirements"]
    fuel = next(i for i in doc["items"] if i["requirement"] == "fuel_utility_data")
    assert FUEL_PACKAGE_NOTE in (fuel.get("note") or "")
    tz = next(i for i in doc["items"] if i["requirement"] == "local_standard_timezone")
    assert "UTC" in (tz.get("consequence") or "")
