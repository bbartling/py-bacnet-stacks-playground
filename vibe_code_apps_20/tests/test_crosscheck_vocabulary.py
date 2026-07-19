"""Tests for the fuel-aware crosscheck enhancements: therms-driven verdicts,
canonical verdict vocabulary, and preserved original values."""

from __future__ import annotations

import pytest

from wattlab.crosscheck import (
    CANONICAL_VERDICTS,
    LEGACY_VERDICT_FROM_CANONICAL,
    crosscheck_measure,
    crosscheck_report,
    legacy_verdict,
)


def test_vocabulary_and_legacy_adapter_cover_each_other():
    assert set(LEGACY_VERDICT_FROM_CANONICAL) == CANONICAL_VERDICTS
    assert set(LEGACY_VERDICT_FROM_CANONICAL.values()) == {
        "in_line", "investigate", "keep_iterating",
    }
    assert legacy_verdict("IN_LINE") == "in_line"
    assert legacy_verdict("ENERGYPLUS_BEHAVIORALLY_IMPLAUSIBLE") == "keep_iterating"


def test_therms_drive_verdict_when_kwh_ratio_missing():
    # Gas-only measure: no electric savings on either side, therms agree.
    row = crosscheck_measure(
        measure_id="HW-RESET",
        ep_savings_kwh=None,
        proxy_savings_kwh=None,
        ep_savings_therms=900.0,
        proxy_savings_therms=1000.0,
    )
    assert row["verdict_basis"] == "therms"
    assert row["agreement_ratio_therms"] == pytest.approx(0.9)
    assert row["verdict_canonical"] == "IN_LINE"
    assert row["verdict"] == "in_line"

    # Wrong-sign therms is behaviorally implausible even without kWh.
    bad = crosscheck_measure(
        measure_id="HW-RESET",
        ep_savings_kwh=None,
        proxy_savings_kwh=None,
        ep_savings_therms=-200.0,
        proxy_savings_therms=1000.0,
    )
    assert bad["verdict_canonical"] == "ENERGYPLUS_BEHAVIORALLY_IMPLAUSIBLE"
    assert bad["verdict"] == "keep_iterating"


def test_kwh_ratio_preferred_over_therms_when_available():
    row = crosscheck_measure(
        measure_id="M",
        ep_savings_kwh=9000.0,
        proxy_savings_kwh=10000.0,
        ep_savings_therms=1.0,
        proxy_savings_therms=1000.0,  # therms wildly off, kWh in line
    )
    assert row["verdict_basis"] == "kwh"
    assert row["verdict_canonical"] == "IN_LINE"


def test_canonical_band_gradations():
    def canonical(ratio_num: float) -> str:
        return crosscheck_measure(
            measure_id="M",
            ep_savings_kwh=ratio_num * 10000.0,
            proxy_savings_kwh=10000.0,
        )["verdict_canonical"]

    assert canonical(0.9) == "IN_LINE"
    # Outside 0.5-2.0 band but within the 2x-relaxed band 0.25-4.0.
    assert canonical(0.3) == "REASONABLE_METHOD_DIFFERENCE"
    assert canonical(3.5) == "REASONABLE_METHOD_DIFFERENCE"
    # Far outside the relaxed band.
    assert canonical(0.1) == "INVESTIGATE_INPUTS"
    assert canonical(10.0) == "INVESTIGATE_INPUTS"
    # Wrong sign.
    assert canonical(-0.5) == "ENERGYPLUS_BEHAVIORALLY_IMPLAUSIBLE"


def test_insufficient_evidence_and_proxy_applicability():
    missing = crosscheck_measure(
        measure_id="M", ep_savings_kwh=None, proxy_savings_kwh=1.0
    )
    assert missing["verdict_canonical"] == "INSUFFICIENT_EVIDENCE"
    assert missing["verdict"] == "investigate"  # legacy behavior preserved

    zero_proxy = crosscheck_measure(
        measure_id="M", ep_savings_kwh=500.0, proxy_savings_kwh=0.0
    )
    assert zero_proxy["verdict_canonical"] == "PROXY_OUTSIDE_APPLICABILITY"

    flagged = crosscheck_measure(
        measure_id="M",
        ep_savings_kwh=9000.0,
        proxy_savings_kwh=10000.0,
        proxy_applicable=False,
    )
    assert flagged["verdict_canonical"] == "PROXY_OUTSIDE_APPLICABILITY"
    assert flagged["verdict"] == "investigate"


def test_originals_preserved_alongside_scaling():
    row = crosscheck_measure(
        measure_id="M",
        ep_savings_kwh=1000.0,
        proxy_savings_kwh=28000.0,
        ep_savings_therms=50.0,
        proxy_savings_therms=1400.0,
        area_scale=28.0,
    )
    assert row["originals"] == {
        "ep_savings_kwh": 1000.0,
        "proxy_savings_kwh": 28000.0,
        "ep_savings_therms": 50.0,
        "proxy_savings_therms": 1400.0,
    }
    # Top-level EP values stay unscaled; scaled values live in *_scaled keys.
    assert row["ep_savings_kwh"] == 1000.0
    assert row["ep_savings_kwh_scaled"] == pytest.approx(28000.0)
    assert row["ep_savings_therms_scaled"] == pytest.approx(1400.0)
    assert row["verdict_canonical"] == "IN_LINE"


def test_report_rolls_up_canonical_overall_verdict():
    rows = [
        {"step": 1, "measure_id": "GOOD", "vs_previous": {"kwh_saved": 9500.0}},
        {"step": 2, "measure_id": "ODD", "vs_previous": {"kwh_saved": 3000.0}},
    ]
    proxies = {
        "GOOD": {"savings_kwh": 10000.0},
        "ODD": {"savings_kwh": 10000.0},  # ratio 0.3 -> method difference
    }
    result = crosscheck_report(rows, proxies)
    assert result["overall_verdict_canonical"] == "REASONABLE_METHOD_DIFFERENCE"
    assert result["overall_verdict"] == "investigate"

    # An applicability flag on the proxy flows through the report path.
    flagged = crosscheck_report(rows, {**proxies, "ODD": {"savings_kwh": 10000.0, "applicable": False}})
    by_id = {m["measure_id"]: m for m in flagged["measures"]}
    assert by_id["ODD"]["verdict_canonical"] == "PROXY_OUTSIDE_APPLICABILITY"

    empty = crosscheck_report([], {})
    assert empty["overall_verdict"] == "no_proxies"
    assert empty["overall_verdict_canonical"] == "INSUFFICIENT_EVIDENCE"
