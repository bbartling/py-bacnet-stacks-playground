"""Sanity gates must reject impossible hybrid kW."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from hybrid_sanity import (  # noqa: E402
    PLANT_PEAK_CAP_KW,
    REJECTED_SPIKE_OUTCOME,
    assert_walk_sane,
    annotate_walk_sanity,
    card_reports_spike_risk,
)


def _fake_walk(hybrid_kw: list[float], delta_kw: list[float] | None = None) -> dict:
    steps = []
    for i, h in enumerate(hybrid_kw):
        d = 0.0 if delta_kw is None else float(delta_kw[i])
        steps.append(
            {
                "step_15": i,
                "hybrid_facility_kw": float(h),
                "delta_facility_kw": d,
                "baseline_facility_kw": float(h) - d,
            }
        )
    return {"steps": steps, "summary": {}}


def test_reject_1000kw_spike():
    w = _fake_walk([100.0] * 10 + [1000.0] + [120.0] * 5)
    reason = assert_walk_sane(w)
    assert reason is not None
    assert reason.code == "hybrid_above_plant_cap"


def test_reject_negative_kw():
    w = _fake_walk([80.0, -50.0, 90.0])
    reason = assert_walk_sane(w)
    assert reason is not None
    assert reason.code == "hybrid_below_floor"


def test_ok_within_cap():
    w = _fake_walk([120.0, 250.0, 298.0, 180.0])
    assert assert_walk_sane(w) is None
    out = annotate_walk_sanity(w)
    assert out["summary"]["sane"] is True
    assert out["summary"]["max_kw_hybrid"] == pytest.approx(298.0)


def test_reject_huge_delta():
    w = _fake_walk([200.0] * 4, delta_kw=[400.0, 10.0, -20.0, 5.0])
    reason = assert_walk_sane(w)
    assert reason is not None
    assert reason.code == "delta_abs_above_cap"


def test_annotate_sets_rejected_flag():
    w = annotate_walk_sanity(_fake_walk([1000.0]))
    assert w["summary"]["outcome_flag"] == REJECTED_SPIKE_OUTCOME
    assert w["sane"] is False
    assert w["summary"]["reject_reasons"]


def test_card_peak_mag_error_gate():
    card = {
        "champion": "extra_trees",
        "cv_recursive_96_heldout": {
            "extra_trees": {"daily_peak_mag_error_kw": PLANT_PEAK_CAP_KW + 50.0}
        },
    }
    reason = card_reports_spike_risk(card)
    assert reason is not None
    assert reason.code == "card_peak_mag_error"
