"""Vibe19 must call OpenFDD vav_health — no local fault equations."""

from __future__ import annotations

import inspect

import pandas as pd

from open_fdd.analytics import vav_health as of_vav
from open_fdd.analytics.occupancy import OccupancySchedule

from app import vav_health as adapter


def test_adapter_reexports_canonical_api():
    assert adapter.vav_health_matrix is of_vav.vav_health_matrix
    assert adapter.vav_health_summary is of_vav.vav_health_summary
    assert adapter.SCHEMA_VERSION == "vav_health_matrix_v1"
    src = inspect.getsource(adapter.compute_vav_health_matrix)
    assert "broken_rule_ids" not in src
    assert "damper_full_open" not in src


def test_missing_damper_is_unknown_not_false():
    idx = pd.date_range("2024-01-02 08:00", periods=40, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {"zone_t": [72.0] * 40, "fan_status": [1.0] * 40},
        index=idx,
    )
    matrix, summary, cfg = adapter.compute_vav_health_matrix(
        {"VAV_1": df},
        building_id="T",
        batch_results=[],
        occupancy=OccupancySchedule(),
        role_map={},
        parent_ahu={"VAV_1": "AHU_1"},
        zone_lo_f=70.0,
        zone_hi_f=75.0,
        poll_seconds=300.0,
    )
    assert list(matrix["parent_ahu"]) == ["AHU_1"]
    row = matrix.iloc[0]
    assert pd.isna(row["rogue_damper"]) or row["rogue_damper"] is None
    assert row["score_label"] == "?/3"
    assert summary["groups"]["?/3"]["count"] == 1
    assert cfg.fingerprint()


def test_grouping_keys():
    empty = pd.DataFrame()
    s = adapter.vav_health_summary(empty)
    assert set(s["groups"]) == {"3/3", "2/3", "1/3", "0/3", "?/3"}
