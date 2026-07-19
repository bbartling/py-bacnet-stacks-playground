"""Mechanical-cooling eligibility, proof ladders, and aggregate semantics."""

from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import (
    MECH_COOL_TOTAL_ID,
    mech_cooling_coverage,
    mech_cooling_oat_bins,
    mech_cooling_run_mask,
)


def typed_frame(equipment_type: str, periods: int | None = None, **roles: list) -> pd.DataFrame:
    """Build a typed equipment frame; role kwargs use snake_case → kebab columns."""
    if not roles:
        raise ValueError("typed_frame requires at least one role series")
    lengths = {len(v) for v in roles.values()}
    if len(lengths) != 1:
        raise ValueError(f"role series length mismatch: {lengths}")
    n = periods if periods is not None else next(iter(lengths))
    idx = pd.date_range("2024-06-01", periods=n, freq="1h", tz="UTC")
    data = {name.replace("_", "-"): values for name, values in roles.items()}
    df = pd.DataFrame(data, index=idx)
    df.attrs["equipment_type"] = equipment_type
    df.attrs["poll_seconds"] = 3600.0
    return df


def assert_bin_invariants(rows: pd.DataFrame) -> None:
    for _, group in rows.groupby("bin_start"):
        individual = group[group.series_kind == "individual_device"].runtime_hours.sum()
        device = group[group.series_kind == "aggregate_device_hours"].runtime_hours.iloc[0]
        active = group[group.series_kind == "aggregate_active_hours"].runtime_hours.iloc[0]
        assert device == pytest.approx(individual)
        assert active <= device + 1e-9
        assert active <= group.valid_elapsed_hours.max() + 1e-9


# --- Classification / proof -------------------------------------------------


def test_direct_chiller_status_is_eligible_with_runtime():
    coverage = mech_cooling_coverage(
        {"CHILLER_1": typed_frame("CHW_PLANT", chiller_status=[0, 1, 1, 0])},
        role_map={},
    )
    row = coverage.iloc[0]
    assert row["included"]
    assert row["eligibility_state"] == "eligible_with_runtime"
    assert row["activity_state"] == "active"
    assert row["proof_role"] == "chiller-status"
    assert row["proof_quality"] == "direct"
    assert row["cooling_technology"] == "chilled_water_plant"
    assert row["compressor_based"]
    assert row["runtime_hours"] == pytest.approx(2.0)
    assert row["status"] == "included"
    assert row["proof"] == "chiller-status"


def test_analog_chiller_power_threshold():
    frame = typed_frame("CHW_PLANT", chiller_power=[0.2, 0.2, 5.0, 0.2])
    mask, proof = mech_cooling_run_mask(frame, equipment_type="CHW_PLANT")
    assert mask is not None
    assert proof == "chiller_power"
    assert list(mask.astype(bool)) == [False, False, True, False]


def test_flat_chiller_status_does_not_hide_active_power_proof():
    frame = typed_frame(
        "CHW_PLANT",
        chiller_status=[0, 0, 0, 0],
        chiller_power=[0.0, 5.0, 6.0, 0.0],
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="CHW_PLANT")
    assert mask is not None
    assert proof == "chiller_power"
    assert list(mask.astype(bool)) == [False, True, True, False]


def test_flat_ahu_status_does_not_hide_active_compressor_command():
    frame = typed_frame(
        "AHU",
        compressor_status=[0, 0, 0, 0],
        compressor_cmd=[0, 1, 1, 0],
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="AHU")
    assert mask is not None
    assert proof == "ahu_dx"
    assert list(mask.astype(bool)) == [False, True, True, False]


def test_flat_zero_chiller_is_eligible_no_runtime():
    coverage = mech_cooling_coverage(
        {"CHILLER_1": typed_frame("CHW_PLANT", chiller_status=[0, 0, 0])},
        role_map={},
    )
    row = coverage.iloc[0]
    assert row["eligibility_state"] == "eligible_no_runtime"
    assert row["included"]
    assert row["runtime_hours"] == 0
    assert row["activity_state"] == "inactive"
    assert row["status"] == "included"
    assert row["proof"] == "chiller-status"

    mask, proof = mech_cooling_run_mask(
        typed_frame("CHW_PLANT", chiller_status=[0, 0, 0]),
        equipment_type="CHW_PLANT",
    )
    assert mask is not None
    assert not mask.any()
    assert proof == "chiller-status"


def test_chw_pump_only_is_excluded_missing_proof():
    frame = typed_frame("CHW_PLANT", chw_pump_status=[0, 1, 1, 0])
    mask, proof = mech_cooling_run_mask(frame, equipment_type="CHW_PLANT")
    assert mask is None
    assert proof == ""

    row = mech_cooling_coverage({"CHW_1": frame}, role_map={}).iloc[0]
    assert not row["included"]
    assert row["eligibility_state"] == "excluded_missing_proof"
    assert row["status"] == "excluded"
    assert "compressor" in row["exclusion_reason"].lower()


def test_flat_chw_pump_does_not_hide_active_chiller_status():
    frame = typed_frame(
        "CHW_PLANT",
        chw_pump_status=[0, 0, 0, 0],
        chiller_status=[0, 1, 1, 0],
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="CHW_PLANT")
    assert mask is not None
    assert proof == "chiller-status"
    assert list(mask.astype(bool)) == [False, True, True, False]


def test_chilled_water_ahu_valve_never_proves_compressor():
    coverage = mech_cooling_coverage(
        {
            "AHU_1": typed_frame("AHU", cooling_valve=[0, 50, 100, 20]),
            "CHILLER_1": typed_frame("CHW_PLANT", chiller_status=[1, 1, 1, 1]),
        },
        role_map={},
    )
    by_id = {r.equipment_id: r for r in coverage.itertuples()}
    assert by_id["AHU_1"].status == "excluded"
    assert by_id["AHU_1"].compressor_based is False
    assert by_id["AHU_1"].cooling_technology == "chilled_water_coil"
    assert "CHW-coil" in by_id["AHU_1"].exclusion_reason
    mask, proof = mech_cooling_run_mask(
        typed_frame("AHU", cooling_valve=[100, 100]),
        equipment_type="AHU",
    )
    assert mask is None
    assert proof == ""


def test_dx_ahu_compressor_status():
    frame = typed_frame("AHU", compressor_status=[0, 1, 1, 0], outside_air_temp=[72] * 4)
    mask, proof = mech_cooling_run_mask(frame, equipment_type="AHU")
    assert mask is not None
    assert proof in {"ahu_dx", "compressor-status"}
    assert int(mask.sum()) == 2
    cov = mech_cooling_coverage({"AHU_DX": frame}, role_map={})
    assert cov.iloc[0]["included"]
    assert cov.iloc[0]["cooling_technology"] == "dx"
    assert cov.iloc[0]["compressor_based"]


def test_two_stage_rtu_unit_active_or_semantics():
    frame = typed_frame(
        "RTU",
        compressor_stage_1=[0, 1, 0, 0],
        compressor_stage_2=[0, 0, 1, 0],
        outside_air_temp=[75] * 4,
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="RTU")
    assert mask is not None
    assert list(mask.astype(bool)) == [False, True, True, False]
    assert "stage" in proof or proof in {"ahu_dx", "compressor-stage"}
    row = mech_cooling_coverage({"RTU_1": frame}, role_map={}).iloc[0]
    assert row["proof_role"] == "compressor-stage"
    assert row["proof_column"] == "compressor-stage-1, compressor-stage-2"


def test_heat_pump_heating_mode_does_not_count_as_cooling():
    frame = typed_frame(
        "HP",
        compressor_status=[1, 1, 1],
        heat_pump_cooling_status=[0, 0, 0],
    )
    mask, _ = mech_cooling_run_mask(frame, equipment_type="HP")
    assert mask is not None
    assert not mask.any()


def test_heat_pump_cooling_mode_counts():
    frame = typed_frame(
        "HP",
        compressor_status=[0, 1, 1, 0],
        heat_pump_cooling_status=[0, 1, 1, 0],
        outside_air_temp=[70.0] * 4,
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="HP")
    assert mask is not None
    assert list(mask.astype(bool)) == [False, True, True, False]
    assert proof
    cov = mech_cooling_coverage({"HP_1": frame}, role_map={})
    assert cov.iloc[0]["included"]
    assert cov.iloc[0]["cooling_technology"] == "heat_pump"
    assert cov.iloc[0]["runtime_hours"] == pytest.approx(2.0)


def test_missing_proof_returns_none_mask():
    frame = typed_frame("AHU", discharge_air_temp=[55.0, 55.0, 55.0])
    mask, proof = mech_cooling_run_mask(frame, equipment_type="AHU")
    assert mask is None
    assert proof == ""


def test_analog_noise_below_threshold_is_eligible_no_runtime():
    frame = typed_frame("CHW_PLANT", chiller_power=[0.05, 0.1, 0.2, 0.0])
    mask, proof = mech_cooling_run_mask(frame, equipment_type="CHW_PLANT")
    assert mask is not None
    assert not mask.any()
    assert proof == "chiller_power"
    cov = mech_cooling_coverage({"CHILLER_N": frame}, role_map={})
    row = cov.iloc[0]
    assert row["eligibility_state"] == "eligible_no_runtime"
    assert row["included"]
    assert row["proof_quality"] == "analog"


def test_vrf_outdoor_compressor_status():
    frame = typed_frame(
        "VRF",
        vrf_outdoor_compressor_status=[0, 1, 1, 0],
        outside_air_temp=[80.0] * 4,
    )
    mask, proof = mech_cooling_run_mask(frame, equipment_type="VRF")
    assert mask is not None
    assert int(mask.sum()) == 2
    assert "vrf" in proof.lower() or proof == "vrf-outdoor-compressor-status"
    cov = mech_cooling_coverage({"VRF_1": frame}, role_map={})
    assert cov.iloc[0]["included"]
    assert cov.iloc[0]["cooling_technology"] == "vrf"
    assert cov.iloc[0]["equipment_type"] == "VRF"


# --- Aggregates / OAT bins --------------------------------------------------


def _oat_frames_non_overlap() -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-06-01", periods=6, freq="1h", tz="UTC")
    oat = [60.0, 60.0, 60.0, 60.0, 60.0, 60.0]
    a = pd.DataFrame({"chiller-status": [1, 1, 0, 0, 0, 0], "outside-air-temp": oat}, index=idx)
    b = pd.DataFrame({"chiller-status": [0, 0, 0, 1, 1, 0], "outside-air-temp": oat}, index=idx)
    a.attrs["equipment_type"] = "CHW_PLANT"
    b.attrs["equipment_type"] = "CHW_PLANT"
    a.attrs["poll_seconds"] = 3600.0
    b.attrs["poll_seconds"] = 3600.0
    return {"CH_A": a, "CH_B": b}


def _oat_frames_overlap() -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-06-01", periods=6, freq="1h", tz="UTC")
    oat = [70.0] * 6
    a = pd.DataFrame({"chiller-status": [1, 1, 1, 0, 0, 0], "outside-air-temp": oat}, index=idx)
    b = pd.DataFrame({"chiller-status": [0, 1, 1, 1, 0, 0], "outside-air-temp": oat}, index=idx)
    a.attrs["equipment_type"] = "CHW_PLANT"
    b.attrs["equipment_type"] = "CHW_PLANT"
    a.attrs["poll_seconds"] = 3600.0
    b.attrs["poll_seconds"] = 3600.0
    return {"CH_A": a, "CH_B": b}


def test_oat_bins_zero_devices_empty_schema():
    bins = mech_cooling_oat_bins({}, role_map={}, include_total=True)
    assert bins.empty
    for col in (
        "series_kind",
        "series_id",
        "runtime_hours",
        "valid_elapsed_hours",
        "equipment_id",
        "bin_start",
        "hours",
    ):
        assert col in bins.columns


def test_oat_bins_one_zero_runtime_device():
    frames = {
        "CHILLER_1": typed_frame(
            "CHW_PLANT",
            chiller_status=[0, 0, 0, 0],
            outside_air_temp=[65.0] * 4,
        )
    }
    cov = mech_cooling_coverage(frames, role_map={})
    assert cov.iloc[0]["eligibility_state"] == "eligible_no_runtime"
    bins = mech_cooling_oat_bins(frames, role_map={}, include_total=True)
    assert bins.empty or (
        bins[bins.series_kind == "individual_device"].empty
        and bins["runtime_hours"].fillna(0).sum() == pytest.approx(0.0)
    )


def test_oat_bins_one_running_device_three_series():
    frames = {
        "CHILLER_1": typed_frame(
            "CHW_PLANT",
            chiller_status=[1, 1, 1, 0],
            outside_air_temp=[72.0] * 4,
        )
    }
    bins = mech_cooling_oat_bins(frames, role_map={}, include_total=True)
    kinds = set(bins["series_kind"])
    assert kinds == {
        "individual_device",
        "aggregate_device_hours",
        "aggregate_active_hours",
    }
    assert_bin_invariants(bins)
    device = bins[bins.series_kind == "aggregate_device_hours"]
    active = bins[bins.series_kind == "aggregate_active_hours"]
    assert (device["equipment_id"] == MECH_COOL_TOTAL_ID).all()
    assert (device["source_kind"] == "total").all()
    assert (active["series_id"] == "aggregate_active_hours").all()
    assert MECH_COOL_TOTAL_ID not in set(active["equipment_id"])
    # Equal when only one device ran
    assert device["runtime_hours"].sum() == pytest.approx(active["runtime_hours"].sum())


def test_oat_bins_non_overlap_active_equals_device_hours():
    bins = mech_cooling_oat_bins(_oat_frames_non_overlap(), role_map={}, include_total=True)
    assert_bin_invariants(bins)
    device = bins[bins.series_kind == "aggregate_device_hours"]["runtime_hours"].sum()
    active = bins[bins.series_kind == "aggregate_active_hours"]["runtime_hours"].sum()
    assert active == pytest.approx(device)


def test_oat_bins_overlap_active_less_than_device_hours():
    bins = mech_cooling_oat_bins(_oat_frames_overlap(), role_map={}, include_total=True)
    assert_bin_invariants(bins)
    device = bins[bins.series_kind == "aggregate_device_hours"]["runtime_hours"].sum()
    active = bins[bins.series_kind == "aggregate_active_hours"]["runtime_hours"].sum()
    # A on @0,1,2 → 3h; B on @1,2,3 → 3h; device=6. OR @0..3 → active=4.
    assert device == pytest.approx(6.0)
    assert active == pytest.approx(4.0)
    assert active < device - 1e-9


def test_oat_bins_three_mixed_devices():
    idx = pd.date_range("2024-06-01", periods=5, freq="1h", tz="UTC")
    oat = [68.0] * 5
    frames = {
        "CH_OFF": typed_frame("CHW_PLANT", chiller_status=[0] * 5, outside_air_temp=oat),
        "CH_A": pd.DataFrame(
            {"chiller-status": [1, 1, 0, 0, 0], "outside-air-temp": oat}, index=idx
        ),
        "AHU_DX": pd.DataFrame(
            {"compressor-status": [0, 1, 1, 0, 0], "outside-air-temp": oat}, index=idx
        ),
    }
    frames["CH_A"].attrs["equipment_type"] = "CHW_PLANT"
    frames["AHU_DX"].attrs["equipment_type"] = "AHU"
    for df in frames.values():
        df.attrs.setdefault("poll_seconds", 3600.0)

    cov = mech_cooling_coverage(frames, role_map={})
    by_id = {r.equipment_id: r for r in cov.itertuples()}
    assert by_id["CH_OFF"].eligibility_state == "eligible_no_runtime"
    assert by_id["CH_A"].included and by_id["AHU_DX"].included

    bins = mech_cooling_oat_bins(frames, role_map={}, include_total=True)
    individuals = bins[bins.series_kind == "individual_device"]
    assert set(individuals["equipment_id"]) == {"CH_A", "AHU_DX"}
    assert_bin_invariants(bins)


def test_oat_bins_irregular_timestamps_and_gap_cap():
    idx = pd.to_datetime(
        [
            "2024-06-01T00:00:00Z",
            "2024-06-01T00:10:00Z",
            "2024-06-01T05:00:00Z",
        ]
    )
    df = pd.DataFrame(
        {"chiller-status": [1, 1, 1], "outside-air-temp": [70.0, 70.0, 70.0]},
        index=idx,
    )
    df.attrs["equipment_type"] = "CHW_PLANT"
    df.attrs["poll_seconds"] = 600.0
    bins = mech_cooling_oat_bins({"CH_1": df}, role_map={}, include_total=True)
    # 10 min + capped 30 min (3x nominal); final row 0 → 40 minutes (rounded to 0.67h)
    runtime = bins[bins.series_kind == "individual_device"]["runtime_hours"].sum()
    assert runtime == pytest.approx(round(40 / 60, 2))


def test_active_hours_uses_conservative_source_cadence_cap():
    fast_idx = pd.to_datetime(
        [
            "2024-06-01T00:00:00Z",
            "2024-06-01T00:10:00Z",
            "2024-06-01T01:00:00Z",
        ]
    )
    slow_idx = pd.to_datetime(
        [
            "2024-06-01T00:00:00Z",
            "2024-06-01T01:00:00Z",
        ]
    )
    fast = pd.DataFrame(
        {"chiller-status": [1, 1, 0], "outside-air-temp": [70.0] * 3},
        index=fast_idx,
    )
    slow = pd.DataFrame(
        {"chiller-status": [0, 1], "outside-air-temp": [70.0] * 2},
        index=slow_idx,
    )
    fast.attrs.update({"equipment_type": "CHW_PLANT", "poll_seconds": 600.0})
    slow.attrs.update({"equipment_type": "CHW_PLANT", "poll_seconds": 3600.0})

    bins = mech_cooling_oat_bins(
        {"FAST": fast, "SLOW": slow}, role_map={}, include_total=True
    )
    device = bins[bins.series_kind == "aggregate_device_hours"].runtime_hours.sum()
    active = bins[bins.series_kind == "aggregate_active_hours"].runtime_hours.sum()
    assert device == pytest.approx(round(40 / 60, 2))
    assert active == pytest.approx(device)


def test_oat_bins_duplicate_timestamps_collapse():
    idx = pd.to_datetime(
        [
            "2024-06-01T00:00:00Z",
            "2024-06-01T00:10:00Z",
            "2024-06-01T00:10:00Z",
            "2024-06-01T00:20:00Z",
        ]
    )
    df = pd.DataFrame(
        {
            "chiller-status": [1, 1, 0, 1],
            "outside-air-temp": [70.0, 70.0, 70.0, 70.0],
        },
        index=idx,
    )
    df.attrs["equipment_type"] = "CHW_PLANT"
    df.attrs["poll_seconds"] = 600.0
    bins = mech_cooling_oat_bins({"CH_1": df}, role_map={}, include_total=True)
    assert_bin_invariants(bins)
    # After dedupe: t0 on, t1 max(1,0)=on, t2 on; durations 10,10,0 → 20 min
    runtime = bins[bins.series_kind == "individual_device"]["runtime_hours"].sum()
    assert runtime == pytest.approx(round(20 / 60, 2))


def test_oat_bins_missing_oat_omits_device_from_bins():
    frames = {
        "CH_1": typed_frame("CHW_PLANT", chiller_status=[1, 1, 1, 0]),
    }
    bins = mech_cooling_oat_bins(frames, role_map={}, prefer_web_oat=False, include_total=True)
    assert bins.empty
    cov = mech_cooling_coverage(frames, role_map={}, prefer_web_oat=False)
    row = cov.iloc[0]
    assert row["eligibility_state"] == "eligible_with_runtime"
    assert row["included"]
    # Three on-samples with zero final duration → 3h; omitted from bins (no OAT)
    assert row["runtime_hours"] == pytest.approx(3.0)


def test_oat_bins_exact_boundary():
    frames = {
        "CH_1": typed_frame(
            "CHW_PLANT",
            chiller_status=[1, 1, 1],
            outside_air_temp=[70.0, 69.9, 75.0],
        )
    }
    bins = mech_cooling_oat_bins(frames, role_map={}, bin_width_f=5.0, include_total=True)
    individuals = bins[bins.series_kind == "individual_device"]
    starts = set(individuals["bin_start"].astype(int))
    assert 70 in starts
    assert 65 in starts
    assert_bin_invariants(bins)

