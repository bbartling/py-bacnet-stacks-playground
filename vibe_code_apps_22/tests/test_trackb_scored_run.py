"""Track B year-aware EPW and scored-runperiod contract."""
from __future__ import annotations

from pathlib import Path

from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.trackb_scored_run import ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD, validate_scored_trackb_run


def test_missing_scored_trajectory_is_not_scored_runtime():
    gate = {
        "completed_successfully": True,
        "severe_count": 2,
        "fatal_count": 0,
        "w2a_low_airflow_by_phase": {"scored_runtime": 3780, "warmup": 0, "sizing": 0},
    }
    out = validate_scored_trackb_run(
        gate=gate,
        returncode=0,
        rows=[],
        expected_day="2026-01-12",
    )
    assert out["ok"] is False
    assert out["status"] == ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD
    assert out["scored_runtime_proven"] is False


def test_valid_scored_run_requires_96_finite_series():
    rows = [
        {
            "day": "2026-01-12",
            "facility_kw": 100.0,
            "timestamp": f"2026-01-12T{h:02d}:{m:02d}:00",
            **{f"z{i}": 70.0 for i in range(6)},
        }
        for h in range(24)
        for m in (0, 15, 30, 45)
    ]
    # helper uses BAS_ZONE_COLS; this test uses the function's facility+temps API
    from eplus_gym.objective import BAS_ZONE_COLS

    rows2 = []
    for i in range(96):
        rec = {"day": "2026-01-12", "facility_kw": 80.0 + i * 0.01, "timestamp": f"t{i}"}
        for col in BAS_ZONE_COLS:
            rec[col] = 70.0
        rows2.append(rec)
    gate = {
        "completed_successfully": True,
        "severe_count": 0,
        "fatal_count": 0,
        "w2a_low_airflow_by_phase": {"scored_runtime": 0, "warmup": 0, "sizing": 0},
    }
    out = validate_scored_trackb_run(gate=gate, returncode=0, rows=rows2, expected_day="2026-01-12")
    assert out["ok"] is True
    assert out["n_intervals"] == 96
    assert out["scored_runtime_proven"] is True
    assert stage_year_aware_epw


def test_rows_from_continuity_payload_reconstructs_96():
    from eplus_gym.control_v2 import ACTION_KEYS
    from eplus_gym.objective import BAS_ZONE_COLS
    from eplus_gym.trackb_scored_run import rows_from_continuity_payload

    payload = {
        "day": "2026-01-12",
        "facility_kw": [40.0] * 96,
        "zone_temps_series_f": {k: [70.0] * 96 for k in ACTION_KEYS},
        "first_runtime_timestamp": "2026-01-12T00:15",
        "last_runtime_timestamp": "2026-01-13T00:00",
    }
    rows = rows_from_continuity_payload(payload, expected_day="2026-01-12")
    assert len(rows) == 96
    gate = {"completed_successfully": True, "severe_count": 0, "fatal_count": 0}
    out = validate_scored_trackb_run(gate=gate, returncode=0, rows=rows, expected_day="2026-01-12")
    assert out["ok"] is True
    assert out["status"] == "VALID_SCORED_RUNPERIOD"
    assert all(col in rows[0] for col in BAS_ZONE_COLS)


def test_two_pass_script_feeds_actual_rows_and_sensitivity():
    src = Path(__file__).resolve().parents[1] / "scripts" / "a04v2_trackb_two_pass.py"
    text = src.read_text(encoding="utf-8")
    assert "rows=[]" not in text
    assert "--sensitivity" in text
    assert "EnergyPlusContinuityPlant" in text
    assert "scored_runperiod_valid" in text


def test_rc0_empty_rows_is_not_valid():
    out = validate_scored_trackb_run(
        gate={"completed_successfully": True, "severe_count": 0, "fatal_count": 0},
        returncode=0,
        rows=[],
        expected_day="2026-01-12",
    )
    assert out["ok"] is False
    assert out["scored_runperiod_valid"] is False
