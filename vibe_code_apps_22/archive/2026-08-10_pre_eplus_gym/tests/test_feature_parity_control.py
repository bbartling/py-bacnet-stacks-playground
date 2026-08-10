"""Golden feature-vector parity for control fixtures (Python SoT).

Documents the contract: stagger_preheat fixture + fixed init → deterministic
feature values at step 20. Both Python and Rust consumers should match these
prefix values (and stagger_min == 60).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from feature_compile_15min import FEATURE_COLS_15MIN_MT  # noqa: E402
from hybrid_rollout import (  # noqa: E402
    build_row,
    init_state_from_contract,
    make_fixture_contract,
)

_GOLDEN = Path(__file__).resolve().parent / "goldens" / "feature_parity_stagger_step20.json"


def _features_at_step(step: int, *, seed: int = 21, dsm_strategy: str = "stagger_preheat"):
    contract = make_fixture_contract(seed=seed, dsm_strategy=dsm_strategy)
    state = init_state_from_contract(contract["init"])
    row, _ = build_row(
        step=step,
        weather=contract["weather_forecast_96"],
        schedule=contract["dsm_control_96"],
        state=state,
        meta=contract["calendar"],
        hdd_acc=0.0,
    )
    return contract, row


def test_golden_json_exists_and_matches_live_row():
    assert _GOLDEN.is_file(), f"missing golden {_GOLDEN}"
    doc = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert doc["stagger_min"] == pytest.approx(60.0)
    assert doc["n_features"] == len(FEATURE_COLS_15MIN_MT)
    assert doc["feature_cols_prefix"] == FEATURE_COLS_15MIN_MT[:10]

    contract, row = _features_at_step(int(doc["step"]), seed=int(doc["seed"]))
    assert contract["dsm_control_96"]["stagger_min"] == pytest.approx(60.0)
    assert row["stagger_min"] == pytest.approx(60.0)
    assert row["strategy_stagger_preheat"] == pytest.approx(1.0)

    live = [float(row[c]) for c in FEATURE_COLS_15MIN_MT[:10]]
    assert live == pytest.approx(doc["values"], abs=1e-9)


def test_golden_documents_control_contract_version():
    contract, _ = _features_at_step(20)
    assert contract.get("control_contract_version") == "control_strategies_v1"
    assert (_APP / "contracts" / "control_strategies_v1" / "stagger_preheat.json").is_file()
