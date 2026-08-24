from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_b59_hvac_operation.py"
SPEC = importlib.util.spec_from_file_location("analyze_b59_hvac_operation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write(path: Path, columns: list[str], rows: list[list[object]]) -> None:
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_streaming_file_analysis_preserves_source_clock_and_regimes(tmp_path):
    path = tmp_path / "rtu_fan_spd.csv"
    _write(
        path,
        ["date", "fan"],
        [
            ["2018-01-01 00:00", 0],
            ["2018-01-01 00:01", 10],
            ["2019-04-01 00:00", 20],
            ["2020-03-18 00:00", 30],
        ],
    )
    spec = MODULE.FileSpec(path.name, "fan", "%", 1, 5.0, sample_every=1)
    result = MODULE.analyze_file(path, spec, chunksize=2)
    assert result["source_clock"] == "timezone-naive recorded source clock"
    assert result["points"]["fan"]["fraction_above_activity_threshold"] == pytest.approx(0.75)
    assert set(result["aggregate_by_regime"]) == {
        "2018",
        "2019_post_reported_march_change",
        "2020_shelter_in_place",
    }
    assert result["material_gaps"] == 2


def test_sat_tracking_and_zone_deadband_exclusions(tmp_path):
    times = ["2020-01-01 00:00", "2020-01-01 00:01"]
    _write(
        tmp_path / "rtu_sa_t.csv",
        ["date"] + [f"rtu_{i:03d}_sa_temp" for i in range(1, 5)],
        [[times[0], 66, 67, 68, 69], [times[1], 70, 70, 70, 70]],
    )
    _write(
        tmp_path / "rtu_sa_t_sp.csv",
        ["date"] + [f"rtu_{i:03d}_sat_sp_tn" for i in range(1, 5)],
        [[times[0], 68, 68, 68, 68], [times[1], 68, 68, 68, 68]],
    )
    tracking = MODULE.analyze_sat_tracking(tmp_path, chunksize=1)
    assert tracking["paired_valid_count"] == 8
    assert tracking["fraction_within_2F"] == 1.0

    setpoint_times = ["2020-01-01 00:00", "2020-01-01 00:05"]
    _write(tmp_path / "zone_temp_sp_c.csv", ["date", "zone_016_cooling_sp"], [[setpoint_times[0], 74], [setpoint_times[1], 0]])
    _write(tmp_path / "zone_temp_sp_h.csv", ["date", "zone_016_heating_sp"], [[setpoint_times[0], 70], [setpoint_times[1], 71]])
    deadbands = MODULE.analyze_zone_deadbands(tmp_path, chunksize=1)
    assert deadbands["common_zone_count"] == 1
    assert deadbands["valid_deadband"]["median_sampled"] == 4.0
    assert deadbands["invalid_zero_or_implausible_excluded"] == 1


def test_paired_analysis_uses_exact_timestamp_intersection_without_resampling(tmp_path):
    columns_a = ["date"] + [f"rtu_{i:03d}_sa_temp" for i in range(1, 5)]
    columns_b = ["date"] + [f"rtu_{i:03d}_sat_sp_tn" for i in range(1, 5)]
    _write(tmp_path / "rtu_sa_t.csv", columns_a, [["2020-01-01 00:00", 68, 68, 68, 68]])
    _write(tmp_path / "rtu_sa_t_sp.csv", columns_b, [["2020-01-01 00:01", 68, 68, 68, 68]])
    _write(
        tmp_path / "rtu_sa_t_sp.csv",
        columns_b,
        [
            ["2020-01-01 00:01", 68, 68, 68, 68],
            ["2020-01-01 00:02", 68, 68, 68, 68],
        ],
    )
    _write(
        tmp_path / "rtu_sa_t.csv",
        columns_a,
        [
            ["2020-01-01 00:00", 66, 66, 66, 66],
            ["2020-01-01 00:01", 70, 70, 70, 70],
        ],
    )
    result = MODULE.analyze_sat_tracking(tmp_path, chunksize=10)
    assert result["paired_valid_count"] == 4
    assert result["aggregate_error"]["mean"] == 2.0


def test_paired_analysis_excludes_all_ambiguous_duplicate_timestamps(tmp_path):
    columns_a = ["date"] + [f"rtu_{i:03d}_sa_temp" for i in range(1, 5)]
    columns_b = ["date"] + [f"rtu_{i:03d}_sat_sp_tn" for i in range(1, 5)]
    _write(
        tmp_path / "rtu_sa_t.csv",
        columns_a,
        [
            ["2020-01-01 00:00", 60, 60, 60, 60],
            ["2020-01-01 00:00", 70, 70, 70, 70],
            ["2020-01-01 00:01", 68, 68, 68, 68],
        ],
    )
    _write(
        tmp_path / "rtu_sa_t_sp.csv",
        columns_b,
        [
            ["2020-01-01 00:00", 68, 68, 68, 68],
            ["2020-01-01 00:01", 68, 68, 68, 68],
        ],
    )
    result = MODULE.analyze_sat_tracking(tmp_path, chunksize=10)
    assert result["paired_valid_count"] == 4
    assert result["aggregate_error"]["mean"] == 0.0
