from __future__ import annotations

import hashlib
import json

import pytest

from eplus_gym.control_v2 import ACTION_KEYS
from eplus_gym.mega.compact_scorecard import (
    PHYSICS_REPAIR_FAILED,
    build_compact_scorecard,
    idf_byte_and_lf_sha256,
    slim_trajectory_rows,
)
from eplus_gym.trackb_scored_run import trajectory_sha256


def _rows(n: int = 96) -> list[dict]:
    out = []
    for i in range(n):
        row = {"local_step": i, "facility_kw": 100.0 + i * 0.1, "day": "2026-01-12"}
        for k in ACTION_KEYS:
            row[k] = 70.0 + 0.01 * i
        out.append(row)
    return out


def test_severe_fatal_never_null_when_zero() -> None:
    gate = {"severe_count": 0, "fatal_count": 0, "w2a_low_airflow_by_phase": {"scored_runtime": 1752}}
    sc = build_compact_scorecard(
        label="development_weekday",
        day="2026-01-12",
        arm="incumbent",
        child_name="a04_child_hp67_scaled_v1",
        child_idf_byte_sha256="a" * 64,
        child_idf_lf_normalized_sha256="b" * 64,
        gate=gate,
        returncode=0,
        payload={"facility_kw": [100.0] * 96, "zone_temps_series_f": {k: [70.0] * 96 for k in ACTION_KEYS}},
    )
    assert sc["severe_count"] == 0
    assert sc["fatal_count"] == 0
    assert sc["physics_status"] == PHYSICS_REPAIR_FAILED
    assert sc["rl_eligible"] is False


def test_trajectory_sha_stable() -> None:
    rows = _rows()
    slim = slim_trajectory_rows(rows)
    a = trajectory_sha256(rows)
    b = trajectory_sha256(json.loads(json.dumps(rows)))
    assert len(slim) == 96
    assert a == b


def test_idf_byte_and_lf_sha() -> None:
    raw = b"line1\r\nline2\r\n"
    byte_sha, lf_sha = idf_byte_and_lf_sha256(raw)
    assert byte_sha == hashlib.sha256(raw).hexdigest()
    assert lf_sha == hashlib.sha256(b"line1\nline2\n").hexdigest()
    assert byte_sha != lf_sha


def test_n_rows_must_be_96_for_valid_scored_runperiod() -> None:
    gate = {"severe_count": 0, "fatal_count": 0, "w2a_low_airflow_by_phase": {"scored_runtime": 0}}
    sc = build_compact_scorecard(
        label="x",
        day="2026-01-12",
        arm="incumbent",
        child_name="test",
        child_idf_byte_sha256="a" * 64,
        child_idf_lf_normalized_sha256="b" * 64,
        gate=gate,
        returncode=0,
        payload={"facility_kw": [100.0] * 96, "zone_temps_series_f": {k: [70.0] * 96 for k in ACTION_KEYS}, "rows": _rows()},
    )
    assert sc["n_rows"] == 96
    assert sc["trajectory_sha256"] is not None


def test_missing_rows_marks_invalid() -> None:
    gate = {"severe_count": 0, "fatal_count": 0}
    sc = build_compact_scorecard(
        label="x",
        day="2026-01-12",
        arm="incumbent",
        child_name="test",
        child_idf_byte_sha256="a" * 64,
        child_idf_lf_normalized_sha256="b" * 64,
        gate=gate,
        returncode=0,
        payload=None,
    )
    assert sc["n_rows"] == 0
    assert sc["scored_runperiod_valid"] is False


def test_label_mismatch_fails_closed() -> None:
    gate = {"severe_count": 0, "fatal_count": 0}
    sc = build_compact_scorecard(
        label="x",
        day="2026-01-12",
        arm="incumbent",
        child_name="test",
        child_idf_byte_sha256="a" * 64,
        child_idf_lf_normalized_sha256="b" * 64,
        gate=gate,
        returncode=0,
        physics_status="WRONG_LABEL",
        rl_eligible=True,
    )
    assert sc["physics_status"] == "WRONG_LABEL"
    assert sc["rl_eligible"] is True
    assert sc["physics_status"] != PHYSICS_REPAIR_FAILED
