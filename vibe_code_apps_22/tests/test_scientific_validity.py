"""Scientific-validity unit tests (no EnergyPlus)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.eplus_err import assert_eplus_quality, parse_eplus_err
from eplus_gym.epw_stage import stage_year_aware_epw, year_qualify_data_periods
from eplus_gym.episode import run_controller_episode
from eplus_gym.objective import BAS_ZONE_COLS, incremental_demand
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.reward import (
    READINESS_FAIL_REWARD,
    operator_pay_2x_v1,
    operator_pay_3x_v1,
    operator_pay_v1,
)
from eplus_gym.rl.split_manifest import assert_no_twin_leakage, build_split_manifest
from eplus_gym.rleplus_path import rleplus_git_sha


def _toy_df(*, peak=100.0, kwh_steps=96, school_ok=True):
    kw = [peak] + [10.0] * (kwh_steps - 1)
    rows = []
    t = 70.0 if school_ok else 60.0
    for i, p in enumerate(kw):
        row = {"local_step": i, "facility_kw": p}
        for c in BAS_ZONE_COLS:
            row[c] = t
        rows.append(row)
    return pd.DataFrame(rows)


def test_readiness_fail_worse_than_valid_operator_pay():
    ok = operator_pay_2x_v1(_toy_df(school_ok=True), school_day=True, billing_floor_kw=0)
    bad = operator_pay_2x_v1(_toy_df(school_ok=False), school_day=True, billing_floor_kw=0)
    assert bad.reward == READINESS_FAIL_REWARD
    assert bad.reward < ok.reward
    assert ok.reward > -1e5


def test_2x_and_3x_are_separate_and_deterministic():
    df = _toy_df(peak=80.0)
    a = operator_pay_2x_v1(df, school_day=True, billing_floor_kw=50.0, baseline_kwh=100.0, baseline_peak_kw=90.0)
    b = operator_pay_3x_v1(df, school_day=True, billing_floor_kw=50.0, baseline_kwh=100.0, baseline_peak_kw=90.0)
    a2 = operator_pay_2x_v1(df, school_day=True, billing_floor_kw=50.0, baseline_kwh=100.0, baseline_peak_kw=90.0)
    assert a.extras["reward_name"] == "operator_pay_2x_v1"
    assert b.extras["reward_name"] == "operator_pay_3x_v1"
    assert a.reward == a2.reward
    assert a.reward != b.reward
    with pytest.raises(ValueError, match="VERIFIED_TARIFF"):
        operator_pay_2x_v1(df, school_day=True, money_mode="VERIFIED_TARIFF")


def test_same_billing_floor_for_pair():
    floor = 180.0
    cand_peak, base_peak = 200.0, 190.0
    _, _, c_cost = incremental_demand(floor, cand_peak, 15.0)
    _, _, b_cost = incremental_demand(floor, base_peak, 15.0)
    assert c_cost == 20.0 * 15.0
    assert b_cost == 10.0 * 15.0


def test_mtd_peak_is_running_max_and_resets_month():
    st = BillingState(floor_kw=0.0)
    assert st.start_of_day(date(2026, 1, 2)) == 0.0
    st.observe_peak(100.0)
    st.observe_peak(80.0)
    assert st.billing_floor_kw() == 100.0
    floor_feb = st.start_of_day(date(2026, 2, 1))
    assert floor_feb == 0.0
    st.observe_peak(50.0)
    st.start_of_day(date(2026, 1, 15))
    assert st.billing_floor_kw() == 100.0


def test_syn_clone_cannot_cross_splits():
    m = build_split_manifest(
        ["2026-01-20", "2026-01-20__syn", "2026-03-01", "2025-11-15"],
        val_months=("2026-03",),
        test_months=("2026-01",),
    )
    assert_no_twin_leakage(m)
    assert "2026-01-20__syn" in m["locked_test"]
    assert "2026-01-20" in m["locked_test"]
    leaked = dict(m)
    leaked["train"] = ["2026-01-20__syn"]
    with pytest.raises(ValueError):
        assert_no_twin_leakage(leaked)


def test_winner_null_without_locked_test(tmp_path: Path):
    from eplus_gym.rl.report_bundle import build_report

    run = tmp_path / "run"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        '{"reward": -1, "day": "2026-01-26", "daily_kwh": 1, "peak_kw": 1, "pre8_violations": 0, "reward_name": "legacy_reward_v1"}\n',
        encoding="utf-8",
    )
    dummy = tmp_path / "dummy.epw"
    dummy.write_text("dummy\n", encoding="utf-8")

    def fake_run_day(**kwargs):
        day = kwargs["day"]
        params = kwargs["ctrl"].params.to_dict()
        return {
            "reward": -2.0,
            "daily_kwh": 1.0,
            "peak_kw": 1.0,
            "pre8_violations": 0,
            "failed": False,
            "params": params,
            "day": day,
        }

    out = build_report(
        site_root=tmp_path,
        epw=dummy,
        champion_idf=dummy,
        run_root=run,
        days=["2026-01-26"],
        random_timesteps=1,
        heuristic_days=False,
        run_day=fake_run_day,
    )
    assert out["winner_mean_reward"] is None
    assert out["winner_is_held_out_eval"] is False


def test_missing_policy_pack_fails_closed(tmp_path: Path):
    from eplus_gym.rl.policy_pack import DailyPolicyPack

    p = DailyPolicyPack(algo="PPO", sb3_zip_bytes=None)
    with pytest.raises(FileNotFoundError):
        p.predict_action(__import__("numpy").zeros(16, dtype="float32"))


def test_forecast_fixture_marked(tmp_path: Path):
    from eplus_gym.rl.field_sidecar import midnight_tick
    from eplus_gym.rl.policy_pack import DailyPolicyPack

    pack = DailyPolicyPack(algo="HEURISTIC")
    pack_path = tmp_path / "p.pkl"
    pack.save(pack_path)
    out = tmp_path / "prop.json"
    prop = midnight_tick(
        pack_path=pack_path,
        day="2026-01-26",
        forecast_source="test_fixture_minus5c_not_openweathermap",
        out_path=out,
        hourly_override=[-5.0] * 24,
    )
    assert prop["forecast_is_test_fixture"] is True
    assert prop["advisory_only"] is True
    assert prop["bacnet_writes"] is False


def test_backend_sha_helper():
    sha = rleplus_git_sha()
    assert sha is None or len(sha) >= 7


def test_severe_blocks_run(tmp_path: Path):
    err = tmp_path / "eplusout.err"
    err.write_text(
        "** Severe ** GetNextEnvironment: weatherfile DATA PERIOD does not have year\n",
        encoding="utf-8",
    )
    end = tmp_path / "eplusout.end"
    end.write_text(
        "EnergyPlus Completed Successfully-- 1 Warning; 2 Severe Errors; Elapsed Time=00hr 00min  1.00sec\n",
        encoding="utf-8",
    )
    gate = parse_eplus_err(err, end)
    assert gate["severe_count"] == 2
    with pytest.raises(ValueError, match="DATA PERIOD"):
        assert_eplus_quality(gate)


def test_year_qualify_epw(tmp_path: Path):
    src = tmp_path / "src.epw"
    src.write_text(
        "LOCATION,X\nDATA PERIODS,1,1,Data,Friday,8/1,7/2\n"
        "2025,8,1,1,60,A7,10\n2026,7,2,24,60,A7,20\n",
        encoding="utf-8",
    )
    dest = tmp_path / "staged.epw"
    rec = stage_year_aware_epw(src, dest)
    text = dest.read_text(encoding="utf-8")
    assert "8/1/2025" in text and "7/2/2026" in text
    assert "Friday" in text
    assert rec["source_sha256"] != rec["staged_sha256"]
    orig = src.read_text(encoding="utf-8")
    assert "8/1,7/2" in orig
    with pytest.raises(ValueError):
        stage_year_aware_epw(src, src)


def test_lookback_returns_96_of_192():
    class FakeCtrl:
        def action(self, step):
            return 0.0

        def action_lookback(self, step):
            return 0.0

    class FakeEnv:
        def __init__(self):
            self.t = 0

        def reset(self):
            return {}, {}

        def close(self):
            return None

        def step(self, _a):
            t = self.t
            self.t += 1
            day = date(2026, 1, 25) if t < 96 else date(2026, 1, 26)
            info = {
                "obs_dict": {
                    "ep_year": float(day.year),
                    "ep_month": float(day.month),
                    "ep_day": float(day.day),
                    "kind_of_sim": 3.0,
                    "warmup": 0.0,
                    "facility_kw": 10.0,
                }
            }
            done = self.t >= 192
            return None, 0.0, done, False, info

    out = run_controller_episode(
        FakeEnv, FakeCtrl(), lookback_days=1, scored_day="2026-01-26", max_steps=None
    )
    assert len(out["rows"]) == 96
    assert len(out["all_rows"]) == 192
    assert all(not r["lookback"] for r in out["rows"])
    assert sum(1 for r in out["all_rows"] if r["lookback"]) == 96


def test_historical_operator_pay_v1_still_zeros():
    br = operator_pay_v1(_toy_df(school_ok=False), school_day=True)
    assert br.reward == 0.0
    assert br.extras["reward_name"] == "operator_pay_v1"


def test_six_zone_actuator_schedule_names_unique():
    from eplus_native.six_zone_htg_stage import ACTION_KEYS, dsm_htg_schedule_name

    names = [dsm_htg_schedule_name(k) for k in ACTION_KEYS]
    assert ACTION_KEYS == ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")
    assert len(names) == len(set(names)) == 6


def test_paired_baseline_key_changes_with_epw():
    from eplus_gym.rl.baseline_cache import paired_baseline_key

    a = paired_baseline_key(
        idf_sha256="a",
        staged_epw_sha256="epw1",
        day="2026-01-26",
        lookback_days=1,
        baseline_name="BAS_INCUMBENT_SCHEDULE",
        energyplus_version="26.1.0",
        reward_name="operator_pay_2x_v1",
    )
    b = paired_baseline_key(
        idf_sha256="a",
        staged_epw_sha256="epw2",
        day="2026-01-26",
        lookback_days=1,
        baseline_name="BAS_INCUMBENT_SCHEDULE",
        energyplus_version="26.1.0",
        reward_name="operator_pay_2x_v1",
    )
    assert a != b


def test_vendored_rleplus_fails_closed(monkeypatch):
    from eplus_gym import rleplus_compat

    monkeypatch.delenv("VIBE22_ALLOW_VENDORED_FALLBACK", raising=False)

    def boom():
        raise FileNotFoundError("no generic runner")

    monkeypatch.setattr("eplus_gym.rleplus_path.ensure_rleplus", boom)
    with pytest.raises(RuntimeError, match="VIBE22_ALLOW_VENDORED_FALLBACK"):
        rleplus_compat.try_rleplus_helpers(allow_vendored_fallback=False)


def test_find_rleplus_refuses_main_without_day_run(tmp_path, monkeypatch):
    from eplus_gym import rleplus_path

    fake = tmp_path / "rllib-energyplus" / "rleplus" / "env"
    fake.mkdir(parents=True)
    (fake / "energyplus.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setenv("RLEPLUS_ROOT", str(tmp_path / "rllib-energyplus"))
    with pytest.raises(FileNotFoundError, match="01c5dc7"):
        rleplus_path.find_rleplus_root()
