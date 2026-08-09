"""Leakage-safe nearest-day + E+ delta benchmark tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_ML = _ROOT / "ml"
sys.path.insert(0, str(_ML))

from nearest_day_delta_benchmark import (  # noqa: E402
    DayRecord,
    STEPS_96,
    TARGET_COLS,
    billing_period_demand_kw,
    build_day_records,
    build_eplus_delta_library,
    eligible_neighbors,
    export_library,
    fit_scale_stats,
    loo_nearest_distances,
    match_eplus_delta,
    ood_threshold_from_loo,
    pointwise_percentiles,
    query_from_inputs,
    rank_neighbors,
    result_to_walk_dict,
    run_simple_hybrid,
)
from feature_compile_heating_dsm import TARGET_COLS as TC  # noqa: E402
from training_profile import TrainingProfile  # noqa: E402


def _synthetic_records(n_days: int = 15, seed: int = 0) -> list[DayRecord]:
    rng = np.random.default_rng(seed)
    records = []
    base = pd.Timestamp("2024-01-01")
    for i in range(n_days):
        day = (base + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        oat = 20 + 5 * np.sin(np.linspace(0, 2 * np.pi, STEPS_96)) + rng.normal(0, 0.5, STEPS_96)
        kw = 40 + 10 * np.sin(np.linspace(0, 2 * np.pi, STEPS_96) - 0.5) + i * 0.1
        zones = np.stack([68 + rng.normal(0, 0.3, STEPS_96) for _ in range(6)], axis=1)
        y = np.column_stack([kw, zones])
        records.append(
            DayRecord(
                day=day,
                is_weekend=1.0 if (base + pd.Timedelta(days=i)).dayofweek >= 5 else 0.0,
                oat_96=oat.tolist(),
                midnight_oat=float(oat[0]),
                midnight_kw=float(kw[0]),
                midnight_zones=zones[0].tolist(),
                y_96x7=y.tolist(),
            )
        )
    return records


def test_target_order_locked():
    assert list(TC) == list(TARGET_COLS)
    assert TARGET_COLS[0] == "facility_kw"
    assert len(TARGET_COLS) == 7


def test_self_and_future_exclusion():
    recs = _synthetic_records(10)
    mid = recs[5].day
    elig = eligible_neighbors(recs, before_day=mid, exclude_day=mid)
    assert mid not in [r.day for r in elig]
    assert all(r.day < mid for r in elig)


def test_complete_day_filtering():
    df = pd.DataFrame(
        {
            "day": ["2024-01-01"] * 50 + ["2024-01-02"] * 96,
            "facility_kw": 1.0,
            "oat_f": 30.0,
            **{z: 68.0 for z in TARGET_COLS[1:]},
            "is_weekend": 0.0,
            "step_15": list(range(50)) + list(range(96)),
        }
    )
    recs = build_day_records(df, require_complete=True, heating_only=False)
    assert [r.day for r in recs] == ["2024-01-02"]


def test_standardized_distance_and_deterministic_ranking():
    recs = _synthetic_records(12)
    scales = fit_scale_stats(recs[:-1])
    q = recs[-1]
    cands = eligible_neighbors(recs, before_day=q.day)
    h1 = rank_neighbors(q, cands, scales, k=5)
    h2 = rank_neighbors(q, cands, scales, k=5)
    assert [h.day for h in h1] == [h.day for h in h2]
    assert h1[0].total_distance <= h1[-1].total_distance


def test_median_p10_p90_shape():
    recs = _synthetic_records(8)
    ys = [np.asarray(r.y_96x7) for r in recs[:5]]
    pct = pointwise_percentiles(ys)
    assert pct["p50"].shape == (96, 7)
    assert pct["p10"].shape == (96, 7)
    assert pct["p90"].shape == (96, 7)
    assert np.all(pct["p10"] <= pct["p50"])
    assert np.all(pct["p50"] <= pct["p90"])


def test_eplus_strategy_matching():
    paired = []
    for arm, kw0 in (("baseline", 40.0), ("dsm", 35.0)):
        for step in range(96):
            paired.append(
                {
                    "pair_id": "2024-01-01__stagger_preheat",
                    "arm": arm,
                    "strategy_id": "stagger_preheat",
                    "step_15": step,
                    "facility_kw": kw0,
                    "oat_f": 25.0,
                    **{z: 68.0 for z in TARGET_COLS[1:]},
                }
            )
    lib = build_eplus_delta_library(pd.DataFrame(paired))
    assert len(lib) == 1
    delta, pid, failed = match_eplus_delta(
        lib,
        strategy_id="stagger_preheat",
        oat_96=[25.0] * 96,
        init_zones=[68.0] * 6,
    )
    assert failed == []
    assert pid is not None
    assert delta is not None
    assert delta.shape == (96, 7)
    assert delta[0, 0] == pytest.approx(-5.0)


def test_ood_refusal():
    recs = _synthetic_records(12)
    scales = fit_scale_stats(recs[:10])
    loo = loo_nearest_distances(recs[:10], scales)
    thresh = ood_threshold_from_loo(loo, percentile=50.0)
    # Far query
    q = query_from_inputs(
        midnight_kw=500.0,
        midnight_zones=[90.0] * 6,
        oat_96=[-40.0] * 96,
        is_weekend=False,
        day_label="2099-01-01",
    )
    res = run_simple_hybrid(
        q,
        recs[:10],
        [],
        scales,
        strategy_id="stagger_preheat",
        k=3,
        ood_threshold=thresh,
        before_day="2099-01-01",
    )
    assert res.ood
    assert res.ood_status == "OUT_OF_DISTRIBUTION"
    assert res.recommend is False


def test_output_shapes_and_kwh():
    recs = _synthetic_records(10)
    scales = fit_scale_stats(recs[:8])
    loo = loo_nearest_distances(recs[:8], scales)
    thresh = ood_threshold_from_loo(loo)
    q = recs[8]
    res = run_simple_hybrid(
        q,
        recs,
        [],
        scales,
        strategy_id="stagger_preheat",
        k=3,
        ood_threshold=thresh,
        before_day=q.day,
    )
    assert res.hybrid_y is not None
    assert res.hybrid_y.shape == (96, 7)
    walk = result_to_walk_dict(res)
    assert len(walk["steps"]) == 96
    from energy_math import quarter_hour_kwh

    assert walk["summary"]["cumulative_kwh_hybrid"] == pytest.approx(
        quarter_hour_kwh(res.hybrid_y[:, 0])
    )


def test_billing_period_demand():
    assert billing_period_demand_kw(100.0, 80.0) == 100.0
    assert billing_period_demand_kw(100.0, 120.0) == 120.0


def test_smoke_cannot_export_desktop_library(tmp_path):
    recs = _synthetic_records(5)
    scales = fit_scale_stats(recs)
    with pytest.raises(PermissionError):
        export_library(
            records=recs,
            eplus_library=[],
            scales=scales,
            ood_threshold=1.0,
            profile=TrainingProfile.from_mode("smoke"),
            out_dir=tmp_path,
            desktop_dir=tmp_path / "desk",
        )


def test_full_deployment_export(tmp_path):
    recs = _synthetic_records(5)
    scales = fit_scale_stats(recs)
    path = export_library(
        records=recs,
        eplus_library=[],
        scales=scales,
        ood_threshold=1.0,
        profile=TrainingProfile.from_mode("full_deployment"),
        out_dir=tmp_path,
        desktop_dir=tmp_path / "desk",
        run_id="test_run",
    )
    assert path.is_file()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema"] == "nearest_day_eplus_delta_v1"
    assert doc["k"] == 10
    assert len(doc["days"]) == 5
    assert (tmp_path / "desk" / path.name).is_file()
    # golden for Rust parity
    golden = {
        "query": {
            "midnight_kw": recs[4].midnight_kw,
            "midnight_zones": recs[4].midnight_zones,
            "oat_96": recs[4].oat_96,
            "is_weekend": recs[4].is_weekend,
            "before_day": recs[4].day,
        },
        "ood_threshold": 1.0,
        "scale_means": scales.means,
        "scale_stds": scales.stds,
        "distance_weights": {
            "weekend_mismatch": 2.0,
            "oat_traj": 1.0,
            "midnight_oat": 0.75,
            "midnight_kw": 0.75,
            "midnight_zones": 1.0,
        },
    }
    res = run_simple_hybrid(
        recs[4],
        recs,
        [],
        scales,
        strategy_id="stagger_preheat",
        k=3,
        ood_threshold=999.0,
        before_day=recs[4].day,
    )
    golden["expected_neighbor_days"] = [n.day for n in res.neighbors]
    golden["expected_nearest_distance"] = res.nearest_distance
    (tmp_path / "desk" / "nearest_day_parity_fixture.json").write_text(
        json.dumps(golden, indent=2), encoding="utf-8"
    )
    # Do NOT overwrite shipped ml/artifacts/fixtures parity file from tests.


def test_python_rust_parity_fixture_exists():
    # Read-only check of shipped fixture if present
    fix = _ROOT / "ml" / "artifacts" / "fixtures" / "nearest_day_parity_fixture.json"
    if fix.is_file():
        doc = json.loads(fix.read_text(encoding="utf-8"))
        assert "expected_neighbor_days" in doc
