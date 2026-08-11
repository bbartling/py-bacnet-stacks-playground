"""Custom / boilerplate rule registration tests."""

from __future__ import annotations

import pandas as pd
import pytest

from app.rules import CANONICAL_RULE_COUNT, RULES, RULES_BY_ID, run_rule
from app.rules.custom_boilerplate import EXAMPLE_SAT_HIGH, EXAMPLE_ZSCORE, make_custom_rule
from app.rules.custom_registry import active_rules, custom_rules


def test_make_custom_rule_requires_prefix():
    with pytest.raises(ValueError, match="CUSTOM-"):
        make_custom_rule(
            rule_id="SAT-HIGH",
            title="bad",
            compute=lambda d, p, poll: pd.Series(False, index=d.index),
            required_roles=["discharge-air-temp"],
            equation="x",
        )


def test_example_sat_high_runs(monkeypatch):
    monkeypatch.setenv("VIBE19_INCLUDE_EXAMPLE_CUSTOM_RULES", "1")
    # Reload registry under env
    import importlib

    import app.rules.custom_registry as reg
    import app.rules as rules_pkg

    importlib.reload(reg)
    importlib.reload(rules_pkg)

    assert any(r.id == "CUSTOM-SAT-HIGH" for r in reg.active_rules())
    idx = pd.date_range("2024-06-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "discharge-air-temp": [70.0] * 6 + [90.0] * 6,
            "fan-status": [1.0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    # Use catalog object directly (avoid stale RULES_BY_ID after reload quirks)
    from app.rules.runner import run_cookbook_rule
    from app.rules.custom_boilerplate import EXAMPLE_SAT_HIGH as rule

    r = run_cookbook_rule(
        rule,
        df,
        equipment_id="AHU_1",
        equipment_kind="ahu",
        poll_seconds=300.0,
        params_by_rule={"CUSTOM-SAT-HIGH": {"sat_hi": 75.0, "confirm_min": 0}},
    )
    assert r.status in {"FAULT", "PASS"}
    assert r.raw_fault is not None
    assert bool(r.raw_fault.iloc[-1])


def test_zscore_boilerplate_shape():
    idx = pd.date_range("2024-01-01", periods=48, freq="5min", tz="UTC")
    # mostly flat then a spike
    vals = [55.0] * 40 + [90.0] * 8
    df = pd.DataFrame({"discharge-air-temp": vals}, index=idx)
    mask = EXAMPLE_ZSCORE.compute(df, {"window_samples": 12, "z_thr": 2.5}, 300.0)
    assert len(mask) == len(df)
    assert mask.dtype == bool


def test_canonical_untouched_by_empty_custom():
    from tests.catalog_contract import pinned_diagnostic_count

    assert CANONICAL_RULE_COUNT == pinned_diagnostic_count()
    # Without example env, custom_rules() is empty by default
    assert custom_rules() == [] or all(r.id.startswith("CUSTOM-") for r in custom_rules())
    assert len([r for r in RULES if not str(r.id).startswith("CUSTOM-")]) == pinned_diagnostic_count()
