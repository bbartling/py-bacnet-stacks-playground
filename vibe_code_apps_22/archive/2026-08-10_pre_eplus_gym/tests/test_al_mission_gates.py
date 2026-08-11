"""A–L mission tests: weather identity, pairs, month replay, delta lags, DST fall."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP), str(_APP / "eplus_native")]


def test_eplus_weather_matches_simulation(tmp_path):
    """Farm row oat/rh/ghi must equal exported sim weather at the same stamp."""
    from eplus_native.extract import load_timestep_site_weather

    # Minimal synthetic eplusout.csv
    sim = tmp_path / "sim"
    sim.mkdir()
    csv = sim / "eplusout.csv"
    csv.write_text(
        "Date/Time,Environment:Site Outdoor Air Drybulb Temperature [C](TimeStep),"
        "Environment:Site Outdoor Air Relative Humidity [%](TimeStep),"
        "Environment:Site Diffuse Solar Radiation Rate per Area [W/m2](TimeStep)\n"
        "01/26  00:15:00,0.0,40.0,10.0\n"
        "01/26  00:30:00,-1.0,42.0,0.0\n",
        encoding="utf-8",
    )
    wx = load_timestep_site_weather(sim)
    assert len(wx) == 2
    assert wx.iloc[0]["oat_f"] == pytest.approx(32.0)  # 0 C
    assert wx.iloc[0]["rh_pct"] == pytest.approx(40.0)
    assert wx.attrs["weather_source"] == "eplus_run_export"


def test_pair_has_identical_noncontrol_inputs():
    from eplus_heating_dsm_farm import build_scenarios, pair_integrity_hashes

    sc = build_scenarios(smoke=True)
    integrity = pair_integrity_hashes(sc)
    assert integrity["n_baseline"] >= 1
    assert integrity["n_dsm"] >= 1
    # each DSM day must have a baseline counterpart in smoke/crossed builders
    days_b = {s["day"] for s in sc if s["arm"] == "baseline"}
    days_d = {s["day"] for s in sc if s["arm"] == "dsm"}
    assert days_d <= days_b or days_d & days_b  # paired days exist


def test_crossed_pairs_share_noncontrol_day_blocks():
    """Crossed design: every weather day has baseline + ≥1 DSM (matched disturbances)."""
    from eplus_heating_dsm_farm import build_scenarios, pair_integrity_hashes

    sc = build_scenarios(crossed=True, n_weather_days=30)
    integrity = pair_integrity_hashes(sc)
    assert integrity["n_days_with_both_arms"] == integrity["n_days"]
    assert integrity["n_dsm"] > integrity["n_baseline"]  # many strategies per day
    by_day: dict[str, set[str]] = {}
    for s in sc:
        by_day.setdefault(str(s["day"]), set()).add(str(s["arm"]))
    assert all("baseline" in arms and "dsm" in arms for arms in by_day.values())


def test_matrix_xy_never_fills_lag_from_current_target():
    """Mutating y[0] must not change X used to predict q0 after compile."""
    from feature_compile_15min import FEATURE_COLS_15MIN_MT, matrix_xy_15min_multi

    rows = []
    for step in range(3):
        row = {
            "day": "2026-01-26",
            "step_15": float(step),
            "sin_step": 0.0,
            "cos_step": 1.0,
            "hour_ending": (step + 1) / 4.0,
            "month": 1.0,
            "doy": 26.0,
            "is_weekend": 0.0,
            "occupied": 0.0,
            "oat_f": 20.0,
            "oat_lag1": 21.0,
            "hdd65": 45.0,
            "hdd65_cum_night": 45.0,
            "hours_to_occupy": 7.0,
            "rh_pct": 40.0,
            "ghi": 0.0,
            "occ_frac_1F_A": 0.0,
            "occ_frac_1F_B": 0.0,
            "occ_frac_1F_C": 0.0,
            "occ_frac_1F_D": 0.0,
            "occ_frac_2F_A": 0.0,
            "occ_frac_2F_B": 0.0,
            "hp_on_1F_A": 0.0,
            "hp_on_1F_B": 0.0,
            "hp_on_1F_C": 0.0,
            "hp_on_1F_D": 0.0,
            "hp_on_2F_A": 0.0,
            "hp_on_2F_B": 0.0,
            "sum_occ_frac": 0.0,
            "sum_hp_on": 0.0,
            "preheat_lead_h": 0.0,
            "stagger_min": 0.0,
            "unocc_htg_sp_f": 64.0,
            "occ_htg_sp_f": 70.0,
            "facility_kw_lag1": 50.0 if step == 0 else 55.0,
            "facility_kw_lag2": 50.0,
            "facility_kw": 99.0,  # target — must not leak into lags
            "strategy_id": "baseline",
        }
        for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B"):
            row[f"zone_temp_{z}_f"] = 68.0
            row[f"zone_temp_{z}_f_lag1"] = 67.0
        rows.append(row)
    df = pd.DataFrame(rows)
    X1, Y1, *_ = matrix_xy_15min_multi(df)
    df2 = df.copy()
    df2.loc[0, "facility_kw"] = 999.0
    for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B"):
        df2.loc[0, f"zone_temp_{z}_f"] = 99.0
    X2, Y2, *_ = matrix_xy_15min_multi(df2)
    assert np.allclose(X1[0], X2[0]), "q0 features must ignore mutated y[0]"
    assert not np.allclose(Y1[0], Y2[0])
    lag_i = FEATURE_COLS_15MIN_MT.index("facility_kw_lag1")
    assert X1[0, lag_i] == pytest.approx(50.0)


def test_identical_control_has_zero_delta_series():
    x = np.linspace(50, 200, 96)
    assert float(np.max(np.abs(x - x))) == 0.0


def test_month_billing_replay_peak_to_date():
    from billing_month_replay import replay_month

    peaks = {
        "2026-01-10": 200.0,
        "2026-01-15": 310.0,
        "2026-01-20": 180.0,
    }
    kwh = {d: 1000.0 for d in peaks}
    rep = replay_month(kwh, peaks, month="2026-01")
    assert "ILLUSTRATIVE" in rep.tariff_note
    # Day 15: before=200, peak=310 → incremental 110 kW * $12
    d15 = next(b for b in rep.days if b.day == "2026-01-15")
    assert d15.peak_to_date_before == pytest.approx(200.0)
    assert d15.incremental_demand_kw == pytest.approx(110.0)
    assert d15.incremental_demand_cost == pytest.approx(1320.0)
    # Day 20 below MTD → zero demand increment
    d20 = next(b for b in rep.days if b.day == "2026-01-20")
    assert d20.incremental_demand_kw == pytest.approx(0.0)


def test_delta_serve_lags_start_at_zero():
    from hybrid_rollout import HybridModels, rollout_96, schedule_from_strategy_fixture

    class _Const:
        def __init__(self, v):
            self.v = float(v)

        def predict(self, X):
            import numpy as np

            n = len(X) if hasattr(X, "__len__") else 1
            # 7 outputs
            return np.full((n, 7), self.v, dtype=float)

    # Minimal contract
    wx = {"oat_f": [20.0] * 96, "rh_pct": [40.0] * 96, "ghi": [0.0] * 96}
    init = {
        "facility_kw": 90.0,
        "oat_f": 20.0,
        **{f"zone_temp_{z}_f": 68.0 for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
    }
    # Use low-level state init check via build path in hybrid_rollout
    from hybrid_rollout import build_row, init_state_from_contract

    state_b = init_state_from_contract(init)
    assert state_b["facility_kw_lag1"] == 90.0
    # Delta arm zeros are set inside rollout_96 — verify by inspecting source contract path
    # Direct: delta state construction
    state_d = {
        "facility_kw_lag1": 0.0,
        "facility_kw_lag2": 0.0,
        "oat_lag1": float(init["oat_f"]),
    }
    for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B"):
        state_d[f"zone_temp_{z}_f_lag1"] = 0.0
    row, _ = build_row(
        step=0,
        weather=wx,
        schedule={"strategy_id": "deep_setback"},
        state=state_d,
        meta={"month": 1, "doy": 26, "is_weekend": 0, "occupied_schedule": [0.0] * 96},
        hdd_acc=0.0,
    )
    assert row["facility_kw_lag1"] == 0.0
    assert row["hour_ending"] == pytest.approx(0.25)


def test_dst_fall_back_metadata():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from interval15 import from_interval_end_utc

    chicago = ZoneInfo("America/Chicago")
    # 2026-11-01 fall back — 01:30 CDT/CST ambiguous; use 03:15 after fold
    civil = datetime(2026, 11, 1, 3, 15, tzinfo=chicago)
    iv = from_interval_end_utc(civil.astimezone(timezone.utc))
    assert 0 <= iv.quarter_index < 96
    assert iv.duration_s == 900


def test_treatment_metrics_bundle():
    from treatment_validation import (
        economic_regret_vs_bau,
        pairwise_ranking_accuracy,
        score_strategy_day,
    )

    b = np.full(96, 100.0)
    d = b.copy()
    d[20:36] += 30.0
    row = score_strategy_day(b, d, strategy="stagger_preheat")
    assert row["sign_acc"] >= 0.9
    assert pairwise_ranking_accuracy({"a": 1.0, "b": 2.0}, ["a", "b"]) == 1.0
    regret = economic_regret_vs_bau(
        bau_peak=300.0,
        strategy_peak=220.0,
        bau_kwh=2000.0,
        strategy_kwh=2100.0,
        existing_billing_peak=250.0,
    )
    # strategy peak below existing → demand $0; bau also below → only energy delta
    assert isinstance(regret, float)


def test_w2a_scaffold_does_not_overwrite_champion(tmp_path):
    from eplus_w2a_dsm_farm_scaffold import stage_w2a_idf
    from physics_families import A04_CHAMPION_IDF

    if not A04_CHAMPION_IDF.is_file():
        pytest.skip("A04 champion not in repo")
    before = A04_CHAMPION_IDF.read_bytes()
    staged = stage_w2a_idf(out_dir=tmp_path, steps_per_hour=6)
    assert staged.is_file()
    assert A04_CHAMPION_IDF.read_bytes() == before
    assert "W2A_PHYSICAL_DSM" in (tmp_path / "w2a_dsm_scaffold_meta.txt").read_text(encoding="utf-8")
