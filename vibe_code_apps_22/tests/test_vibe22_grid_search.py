"""Unit tests for Vibe22 grid-search comparator (no EnergyPlus)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from eplus_gym.rl.day_ahead_tariff import (
    TariffContractError,
    expand_hourly_to_96,
    flat_plus_demand_fixture,
    illustrative_dynamic_hourly_fixture,
    load_day_ahead_tariff,
    provenance_hash,
    validate_day_ahead_tariff,
    write_default_fixtures,
)
from eplus_gym.rl.grid_search_menu import build_candidate_menu, day_fingerprint
from eplus_gym.rl.grid_search_select import (
    aggregate_candidate,
    compare_grid_vs_rl,
    select_grid_validation_leader,
)
from eplus_gym.rl.research_spaces import decode_discrete_research_v3, discrete_n_research_v3
from eplus_gym.rl.reward_v2 import score_day_v2


def test_discrete_n_from_code_not_hardcoded():
    n = discrete_n_research_v3()
    assert n == 2 + 3 * 4 * 3 * 4
    menu = build_candidate_menu()
    assert menu["declared_action_count"] == n
    assert menu["continuous_68_index"] == 0
    assert menu["continuous_70_index"] == 1


def test_action_index_never_wraps():
    n = discrete_n_research_v3()
    with pytest.raises(ValueError, match="wrap is forbidden"):
        decode_discrete_research_v3(n, day="2025-12-15")
    with pytest.raises(ValueError, match="wrap is forbidden"):
        decode_discrete_research_v3(-1, day="2025-12-15")


def test_schedule_fingerprint_dedupe_and_school_collapse():
    menu = build_candidate_menu(days=["2025-12-15", "2025-12-20"])
    # Weekend collapse: many indices share fingerprints
    assert menu["unique_by_day"]["2025-12-20"] < menu["declared_action_count"]
    assert menu["n_unique_fixed_policies"] <= menu["declared_action_count"]
    # Same index same day → same fingerprint
    assert day_fingerprint(2, "2025-12-15") == day_fingerprint(2, "2025-12-15")


def test_hourly_to_96_and_invalid_tariff(tmp_path: Path):
    qh = expand_hourly_to_96([0.1] * 24)
    assert len(qh) == 96
    with pytest.raises(TariffContractError):
        expand_hourly_to_96([0.1] * 23)
    write_default_fixtures(tmp_path)
    ok = load_day_ahead_tariff(tmp_path / "flat_plus_demand.json")
    assert len(ok["_quarter_hour_prices"]) == 96
    bad = flat_plus_demand_fixture()
    bad["energy_prices"] = [float("nan")] * 24
    bad["provenance"] = {"hash": provenance_hash(bad)}
    with pytest.raises(TariffContractError):
        validate_day_ahead_tariff(bad)
    neg = flat_plus_demand_fixture()
    neg["energy_prices"] = [-0.1] * 24
    neg["provenance"] = {"hash": provenance_hash(neg)}
    with pytest.raises(TariffContractError):
        validate_day_ahead_tariff(neg)


def test_tariff_only_rescore_preserves_kwh_peak():
    fac = list(np.linspace(50.0, 150.0, 96))
    zones = {f"z{i}": [70.0] * 96 for i in range(6)}
    # Map to ACTION_KEYS-compatible names via score_day helper expects BAS cols —
    # use list-of-series form
    from eplus_gym.control_v2 import ACTION_KEYS

    zmap = {k: [68.5] * 96 for k in ACTION_KEYS}
    flat = flat_plus_demand_fixture()
    dyn = illustrative_dynamic_hourly_fixture()
    r1 = score_day_v2(
        day="2025-12-15",
        candidate_facility_kw=fac,
        candidate_zone_temps_f=zmap,
        baseline_facility_kw=fac,
        baseline_zone_temps_f=zmap,
        rate_kwh=list(np.repeat(flat["energy_prices"], 4)),
        demand_rate=float(flat["demand_rate_usd_per_kw"]),
        mtd_peak_kw=0.0,
    )
    r2 = score_day_v2(
        day="2025-12-15",
        candidate_facility_kw=fac,
        candidate_zone_temps_f=zmap,
        baseline_facility_kw=fac,
        baseline_zone_temps_f=zmap,
        rate_kwh=list(np.repeat(dyn["energy_prices"], 4)),
        demand_rate=float(dyn["demand_rate_usd_per_kw"]),
        mtd_peak_kw=0.0,
    )
    assert abs(r1.candidate["day_peak_kw"] - r2.candidate["day_peak_kw"]) < 1e-9
    assert abs(r1.candidate["daily_kwh"] - r2.candidate["daily_kwh"]) < 1e-9
    assert abs(r1.candidate["energy_cost"] - r2.candidate["energy_cost"]) > 1e-6


def test_selection_tiebreak_and_readiness_school_only():
    school = ["2025-12-15", "2025-12-16", "2025-12-17", "2025-12-18", "2025-12-19"]

    def rows(ready_school: bool, cost_energy: float, peak: float) -> list[dict]:
        out = []
        for d in school:
            out.append(
                {
                    "day": d,
                    "valid": True,
                    "energy_cost": cost_energy / 5.0,
                    "incremental_demand_cost": 0.0,
                    "peak_kw": peak,
                    "daily_kwh": 1.0,
                    "readiness_ok": ready_school,
                    "occupied_dh": 1.0,
                    "movement": 0.5,
                }
            )
        # non-school auto-pass should not count
        out.append(
            {
                "day": "2025-12-20",
                "valid": True,
                "energy_cost": 0.0,
                "incremental_demand_cost": 0.0,
                "peak_kw": peak,
                "daily_kwh": 1.0,
                "readiness_ok": True,
                "occupied_dh": 0.0,
                "movement": 0.0,
            }
        )
        return out

    a = aggregate_candidate(
        candidate_id="discrete_1",
        action_index=1,
        day_rows=rows(True, 100.0, 200.0),
        checked_school_days=school,
    )
    b = aggregate_candidate(
        candidate_id="discrete_0",
        action_index=0,
        day_rows=rows(True, 100.0, 190.0),
        checked_school_days=school,
    )
    c = aggregate_candidate(
        candidate_id="discrete_2",
        action_index=2,
        day_rows=rows(False, 50.0, 100.0),
        checked_school_days=school,
    )
    assert a["readiness"]["checked_school_days"] == 5
    assert a["eligible"]
    assert not c["eligible"]
    sel = select_grid_validation_leader([a, b, c])
    assert sel["grid_validation_leader"] == "discrete_0"  # same cost, lower peak
    assert compare_grid_vs_rl(grid=a, rl_total=120.0, rl_peak=210.0, rl_ready=True, screen_exhaustive=True) == (
        "GRID_LOWER_COST_AND_READY"
    )


def test_no_candidate_as_baseline_and_no_synthetic_fallback():
    from eplus_gym.rl.research_poc import reject_candidate_as_baseline

    with pytest.raises(ValueError, match="candidate-as-baseline"):
        reject_candidate_as_baseline({"sha": "abc"}, {"sha": "abc"})
    with pytest.raises(ValueError, match="candidate-as-baseline"):
        reject_candidate_as_baseline({"sha": ""}, {"sha": "x"})


def test_billing_floors_open_at_zero_on_dec15():
    from eplus_gym.control_v2 import ACTION_KEYS

    fac = [100.0] * 96
    z = {k: [70.0] * 96 for k in ACTION_KEYS}
    r = score_day_v2(
        day="2025-12-15",
        candidate_facility_kw=fac,
        candidate_zone_temps_f=z,
        baseline_facility_kw=[90.0] * 96,
        baseline_zone_temps_f=z,
        mtd_peak_kw=0.0,
        rate_kwh=0.11,
        demand_rate=12.0,
    )
    assert r.candidate["old_floor_kw"] == 0.0
    assert r.candidate["demand_increment"] == 12.0 * 100.0
