from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from vibe23.b59_data import (
    B59_BINDING_SCHEMA,
    B59_TIMEZONE,
    B59DataError,
    build_electricity_targets,
    infer_schedule_summary,
    telemetry_audit,
    validate_point_bindings,
)


def _csv(path, columns, rows):
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _config():
    return {
        "schema": B59_BINDING_SCHEMA,
        "timezone": B59_TIMEZONE,
        "electricity": {
            "path": "ele.csv",
            "timestamp_column": "date",
            "source_timezone": "UTC",
            "time_basis_status": "test fixture explicit UTC",
            "columns": ["mels_S", "mels_N", "lig_S", "hvac_S", "hvac_N"],
        },
        "occupancy": {
            "path": "occ.csv",
            "timestamp_column": "date",
            "source_timezone": "UTC",
            "time_basis_status": "test fixture explicit UTC",
            "columns": ["occ"],
        },
        "rtu": {
            "path": "rtu.csv",
            "timestamp_column": "date",
            "source_timezone": "UTC",
            "time_basis_status": "test fixture explicit UTC",
            "columns": ["rtu_001_sf_vfd_spd_fbk_tn"],
        },
    }


def _raw_fixture(tmp_path):
    _csv(tmp_path / "ele.csv", ["date", "mels_S", "mels_N", "lig_S", "hvac_S", "hvac_N"], [
        ["2019-01-01 00:00", 1, 2, 3, 4, 5], ["2019-01-01 00:15", 1, 2, 3, 4, 5],
        ["2019-01-01 00:30", 1, 2, 3, 4, 5], ["2019-01-01 00:45", 1, 2, 3, 4, 5],
    ])
    _csv(tmp_path / "occ.csv", ["date", "occ"], [["2019-01-01 00:00", 0], ["2019-01-01 00:01", 1]])
    _csv(tmp_path / "rtu.csv", ["date", "rtu_001_sf_vfd_spd_fbk_tn"], [["2019-01-01 00:00", 0], ["2019-01-01 00:01", 1]])
    return validate_point_bindings(_config(), tmp_path)


def test_exact_binding_validation_and_target_provenance(tmp_path):
    bindings = _raw_fixture(tmp_path)
    target, monthly, provenance = build_electricity_targets(bindings)
    assert target["office_total_kw"].tolist() == [15.0] * 4
    assert monthly.iloc[0]["energy_kwh"] == pytest.approx(15.0)
    assert monthly.iloc[0]["mels_bound_kwh"] == pytest.approx(3.0)
    assert monthly.iloc[0]["lighting_bound_kwh"] == pytest.approx(3.0)
    assert monthly.iloc[0]["hvac_panels_bound_kwh"] == pytest.approx(9.0)
    assert provenance["office_total_definition"] == "mels_S + mels_N + lig_S + hvac_S + hvac_N"
    assert provenance["missing_end_uses"] == ["lig_N"]
    assert provenance["source_timestamp_timezone"] == "UTC"
    assert not provenance["monthly_coverage_pass"]
    assert provenance["source_sha256"] == hashlib.sha256((tmp_path / "ele.csv").read_bytes()).hexdigest()


def test_rejects_guessed_binding_column(tmp_path):
    _raw_fixture(tmp_path)
    config = _config()
    config["electricity"]["columns"][-1] = "guessed_hvac"
    with pytest.raises(B59DataError, match="exactly"):
        validate_point_bindings(config, tmp_path)


@pytest.mark.parametrize("rows, match", [
    ([["2019-01-01 00:00", 1, 2, 3, 4, 5], ["2019-01-01 00:30", 1, 2, 3, 4, 5]], "gaps"),
    ([["2019-01-01 00:00", 1, 2, 3, 4, 5], ["2019-01-01 00:00", 1, 2, 3, 4, 5]], "duplicate"),
    ([["2019-01-01 00:00", 1, 2, 3, 4, ""], ["2019-01-01 00:15", 1, 2, 3, 4, 5]], "null"),
])
def test_target_fails_closed_on_bad_raw_data(tmp_path, rows, match):
    bindings = _raw_fixture(tmp_path)
    _csv(tmp_path / "ele.csv", ["date", "mels_S", "mels_N", "lig_S", "hvac_S", "hvac_N"], rows)
    with pytest.raises(B59DataError, match=match):
        build_electricity_targets(bindings)


def test_audit_and_schedule_summary_use_small_fixture(tmp_path):
    bindings = _raw_fixture(tmp_path)
    audit = telemetry_audit(bindings.electricity_path, "date", bindings.electricity_components)
    assert audit["year_rows"] == {"2019": 4}
    assert audit["regularity_status"] == "PASS"
    summary = infer_schedule_summary(
        bindings.occupancy_path,
        "date",
        bindings.occupancy_columns,
        source_timezone=bindings.occupancy_source_timezone,
    )
    assert summary["timezone"] == B59_TIMEZONE
    assert summary["activity_by_weekday_quarter_hour"]


def test_window_is_half_open_timezone_explicit_and_ignores_bad_rows_outside_it(tmp_path):
    bindings = _raw_fixture(tmp_path)
    _csv(
        tmp_path / "ele.csv",
        ["date", "mels_S", "mels_N", "lig_S", "hvac_S", "hvac_N"],
        [
            ["2019-01-01 00:00", "", 2, 3, 4, 5],
            ["2020-01-01 00:00", 1, 2, 3, 4, 5],
            ["2020-01-01 00:15", 1, 2, 3, 4, 5],
            ["2020-01-01 00:30", 1, 2, 3, 4, 5],
            ["2020-01-01 00:45", 1, 2, 3, 4, 5],
            ["2020-01-01 01:00", "", 2, 3, 4, 5],
        ],
    )
    target, _, provenance = build_electricity_targets(
        bindings,
        start="2020-01-01T00:00:00Z",
        end="2020-01-01T01:00:00Z",
    )
    assert len(target) == 4
    assert provenance["selected_window"]["end_exclusive"] == "2020-01-01T01:00:00+00:00"
    with pytest.raises(B59DataError, match="explicit timezone"):
        build_electricity_targets(bindings, start="2020-01-01", end="2020-01-01 01:00")
