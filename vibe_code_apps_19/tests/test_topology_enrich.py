"""Topology enrich (ahu_sat) + VAV-AHU-LEAVE leave-temp rule."""

from __future__ import annotations

import pandas as pd

from app.data_model_tree import build_data_model_tree
from app.rules import RULES_BY_ID, run_rule
from app.rules.runner import run_batch
from app.topology_enrich import (
    AHU_SAT_ROLE,
    enrich_frames_with_ahu_feeds,
    invert_vav_to_ahu,
    stamp_feed_attrs,
)


def _idx(n: int = 6) -> pd.DatetimeIndex:
    return pd.date_range("2024-06-01", periods=n, freq="5min", tz="UTC")


def test_invert_vav_to_ahu():
    assert invert_vav_to_ahu({"VAV_1": "AHU_1", "VAV_2": "AHU_1"}) == {
        "AHU_1": ["VAV_1", "VAV_2"]
    }


def test_enrich_copies_parent_sat():
    idx = _idx()
    ahu = pd.DataFrame({"discharge-air-temp": [55.0] * 6}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    vav = pd.DataFrame(
        {"vav-discharge-air-temp": [55.0, 55.0, 70.0, 70.0, 70.0, 70.0], "zone-airflow": [100.0] * 6},
        index=idx,
    )
    vav.attrs["equipment_type"] = "VAV"
    frames = {"AHU_1": ahu, "VAV_1": vav}
    notes = enrich_frames_with_ahu_feeds(frames, {"VAV_1": "AHU_1"})
    assert notes
    assert AHU_SAT_ROLE in vav.columns
    assert float(vav[AHU_SAT_ROLE].iloc[0]) == 55.0
    assert vav.attrs.get("fed_by") == "AHU_1"


def test_stamp_feed_attrs():
    idx = _idx(2)
    ahu = pd.DataFrame({"discharge-air-temp": [55.0, 55.0]}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    vav = pd.DataFrame({"vav-discharge-air-temp": [55.0, 55.0]}, index=idx)
    vav.attrs["equipment_type"] = "VAV"
    frames = {"AHU_1": ahu, "VAV_1": vav}
    stamp_feed_attrs(frames, {"VAV_1": "AHU_1"})
    assert vav.attrs["fed_by"] == "AHU_1"
    assert ahu.attrs["feeds"] == ["VAV_1"]


def test_data_model_tree_feeds():
    idx = _idx(2)
    ahu = pd.DataFrame({"discharge-air-temp": [55.0, 55.0]}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    vav = pd.DataFrame({"vav-discharge-air-temp": [55.0, 55.0]}, index=idx)
    vav.attrs["equipment_type"] = "VAV"
    tree = build_data_model_tree(
        {"AHU_1": ahu, "VAV_1": vav},
        {},
        building_id="B1",
        vav_to_ahu={"VAV_1": "AHU_1"},
    )
    by_id = {e.equipment_id: e for e in tree.equipment}
    assert by_id["VAV_1"].fed_by == "AHU_1"
    assert by_id["AHU_1"].feeds == ["VAV_1"]
    topo = tree.topology_rows()
    assert {"equipment_id": "AHU_1", "relation": "feeds", "related_ids": "VAV_1", "related_count": 1} in topo
    assert {"equipment_id": "VAV_1", "relation": "fedBy", "related_ids": "AHU_1", "related_count": 1} in topo
    point_cols = set(tree.to_rows()[0]) if tree.to_rows() else set()
    assert "fed_by" not in point_cols and "feeds" not in point_cols


def test_vav_ahu_leave_skipped_without_ahu_sat():
    idx = _idx()
    df = pd.DataFrame(
        {"vav-discharge-air-temp": [70.0] * 6, "zone-airflow": [100.0] * 6},
        index=idx,
    )
    df.attrs["equipment_id"] = "VAV_1"
    df.attrs["equipment_type"] = "VAV"
    r = run_rule("VAV-AHU-LEAVE", df, {"confirm_min": 0, "delta_f": 8.0}, 300.0)
    assert r.status == "SKIPPED_MISSING_ROLES"
    assert "ahu-discharge-air-temp" in (r.missing_roles or [])


def test_vav_ahu_leave_faults_when_delta_large():
    idx = _idx()
    df = pd.DataFrame(
        {
            "vav-discharge-air-temp": [70.0] * 6,
            "ahu-discharge-air-temp": [55.0] * 6,
            "zone-airflow": [100.0] * 6,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "VAV_1"
    df.attrs["equipment_type"] = "VAV"
    r = run_rule(
        "VAV-AHU-LEAVE",
        df,
        {"confirm_min": 0, "delta_f": 8.0, "flow_on_min": 25.0},
        300.0,
        require_operational_gates=False,
    )
    assert r.applicable
    assert r.status == "FAULT"


def test_vav_ahu_leave_pass_within_band():
    idx = _idx()
    df = pd.DataFrame(
        {
            "vav-discharge-air-temp": [56.0] * 6,
            "ahu-discharge-air-temp": [55.0] * 6,
            "zone-airflow": [100.0] * 6,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "VAV_1"
    df.attrs["equipment_type"] = "VAV"
    r = run_rule(
        "VAV-AHU-LEAVE",
        df,
        {"confirm_min": 0, "delta_f": 8.0},
        300.0,
        require_operational_gates=False,
    )
    assert r.status == "PASS"


def test_run_batch_enriches_and_evaluates():
    assert "VAV-AHU-LEAVE" in RULES_BY_ID
    idx = _idx()
    ahu = pd.DataFrame({"discharge-air-temp": [55.0] * 6, "fan-status": [1] * 6}, index=idx)
    ahu.attrs.update({"equipment_id": "AHU_1", "equipment_type": "AHU", "poll_seconds": 300.0})
    vav = pd.DataFrame(
        {
            "vav-discharge-air-temp": [70.0] * 6,
            "zone-airflow": [100.0] * 6,
            "fan-status": [1] * 6,
        },
        index=idx,
    )
    vav.attrs.update({"equipment_id": "VAV_1", "equipment_type": "VAV", "poll_seconds": 300.0})
    results = run_batch(
        {"AHU_1": ahu, "VAV_1": vav},
        vav_to_ahu={"VAV_1": "AHU_1"},
        equipment_filter={"VAV_1"},
    )
    leave = [r for r in results if r.rule_id == "VAV-AHU-LEAVE"]
    assert leave
    assert leave[0].status in {"FAULT", "PASS", "SKIPPED_EQUIPMENT_OFF"}
    assert leave[0].status != "SKIPPED_MISSING_ROLES"
