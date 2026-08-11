"""Control strategy fixture parity (farm SoT → hybrid_rollout)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from feature_compile_heating_dsm import HP_ON_COLS, OCC_FRAC_COLS  # noqa: E402
from hybrid_rollout import (  # noqa: E402
    STEPS,
    build_row,
    init_state_from_contract,
    load_strategy_control,
    make_fixture_contract,
    schedule_from_strategy_fixture,
)

_CONTROL_DIR = _APP / "contracts" / "control_strategies_v1"
_EXPORT = _APP / "scripts" / "export_control_contracts.py"


def test_export_script_and_fixtures_present():
    assert _EXPORT.is_file()
    for sid in ("baseline", "stagger_preheat"):
        assert (_CONTROL_DIR / f"{sid}.json").is_file()
    assert (_CONTROL_DIR / "index.json").is_file()


def test_load_strategy_control_baseline_and_stagger():
    base = load_strategy_control("baseline")
    stag = load_strategy_control("stagger_preheat")
    assert base["strategy_id"] == "baseline"
    assert stag["strategy_id"] == "stagger_preheat"
    assert len(base["steps"]) == STEPS
    assert len(stag["steps"]) == STEPS
    assert float(stag["meta"]["stagger_min"]) == pytest.approx(60.0)


def test_schedule_from_strategy_fixture_length_96():
    for sid in ("baseline", "stagger_preheat"):
        sched = schedule_from_strategy_fixture(sid)
        assert sched["strategy_id"] == sid
        for c in OCC_FRAC_COLS + HP_ON_COLS:
            assert len(sched[c]) == STEPS
        assert sched["stagger_min"] == (
            pytest.approx(60.0) if sid == "stagger_preheat" else pytest.approx(0.0)
        )


def test_prbs_raises():
    with pytest.raises(ValueError, match="PRBS"):
        load_strategy_control("prbs_heat")
    with pytest.raises(ValueError, match="PRBS"):
        schedule_from_strategy_fixture("prbs_a")


def test_build_row_uses_stagger_preheat_fixture_knobs():
    contract = make_fixture_contract(seed=21, dsm_strategy="stagger_preheat")
    assert contract["dsm_control_96"]["stagger_min"] == pytest.approx(60.0)
    state = init_state_from_contract(contract["init"])
    meta = contract["calendar"]
    weather = contract["weather_forecast_96"]
    # Spot-check morning preheat steps (HE 5–7 → steps 20–28).
    for t in (0, 20, 24, 28, 40):
        row, _ = build_row(
            step=t,
            weather=weather,
            schedule=contract["dsm_control_96"],
            state=state,
            meta=meta,
            hdd_acc=0.0,
        )
        assert row["stagger_min"] == pytest.approx(60.0)
        assert row["strategy_stagger_preheat"] == pytest.approx(1.0)
        assert row["strategy_baseline"] == pytest.approx(0.0)
        assert row["preheat_lead_h"] == pytest.approx(
            float(contract["dsm_control_96"]["preheat_lead_h"])
        )
