"""Tests for wattlab.finance economics and wattlab.crosscheck verdicts."""

from __future__ import annotations

import json

import pytest

from wattlab.crosscheck import (
    crosscheck_from_report,
    crosscheck_measure,
    crosscheck_report,
    g14_gates,
    main as crosscheck_main,
)
from wattlab.finance import (
    capital_plan,
    escalated_cash_flows,
    measure_economics,
    npv,
    plan_to_csv,
    simple_payback_years,
)


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

def test_escalated_cash_flows_and_npv():
    flows = escalated_cash_flows(1000.0, 3, escalation_rate=0.10)
    assert flows == pytest.approx([1000.0, 1100.0, 1210.0])
    # NPV at 0% discount is just the sum minus cost.
    assert npv(flows, discount_rate=0.0, initial_cost=3000.0) == pytest.approx(310.0)
    # NPV at 10% discount of the 10%-escalated flows: each year PV ~ 1000/1.1.
    value = npv(flows, discount_rate=0.10, initial_cost=0.0)
    assert value == pytest.approx(1000.0 / 1.1 * 3)


def test_simple_payback():
    assert simple_payback_years(10000.0, 2500.0) == pytest.approx(4.0)
    assert simple_payback_years(10000.0, 0.0) is None


def test_measure_economics_row():
    row = measure_economics(
        measure_id="SCHED-1",
        title="Start/stop optimization",
        implementation_cost_usd=12000.0,
        kwh_saved=25000.0,
        therms_saved=1000.0,
        elec_rate_usd_per_kwh=0.12,
        gas_rate_usd_per_therm=0.80,
        measure_life_years=10,
        discount_rate=0.05,
        escalation_rate=0.0,
    )
    # 25000*0.12 + 1000*0.80 = 3800 USD/yr.
    assert row["annual_cost_saved_usd"] == pytest.approx(3800.0)
    assert row["simple_payback_years"] == pytest.approx(12000.0 / 3800.0, abs=0.01)
    assert row["lifetime_savings_usd"] == pytest.approx(38000.0)
    assert row["roi_over_life"] == pytest.approx((38000.0 - 12000.0) / 12000.0, abs=1e-3)
    assert row["npv_usd"] == pytest.approx(
        sum(3800.0 / 1.05 ** (y + 1) for y in range(10)) - 12000.0, abs=0.01
    )


def test_capital_plan_sorts_by_payback_and_totals():
    fast = measure_economics(
        measure_id="FAST", implementation_cost_usd=1000.0, kwh_saved=10000.0,
        escalation_rate=0.0,
    )
    slow = measure_economics(
        measure_id="SLOW", implementation_cost_usd=50000.0, kwh_saved=10000.0,
        escalation_rate=0.0,
    )
    plan = capital_plan([slow, fast])
    assert [m["measure_id"] for m in plan["measures"]] == ["FAST", "SLOW"]
    assert plan["totals"]["implementation_cost_usd"] == pytest.approx(51000.0)
    assert plan["totals"]["kwh_saved"] == pytest.approx(20000.0)
    csv_text = plan_to_csv(plan)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("measure_id,")
    assert lines[1].startswith("FAST,")
    assert lines[-1].startswith("TOTAL,")


# ---------------------------------------------------------------------------
# Crosscheck
# ---------------------------------------------------------------------------

def test_crosscheck_measure_verdicts():
    in_line = crosscheck_measure(
        measure_id="M1", ep_savings_kwh=9000.0, proxy_savings_kwh=10000.0
    )
    assert in_line["verdict"] == "in_line"
    assert in_line["agreement_ratio"] == pytest.approx(0.9)

    investigate = crosscheck_measure(
        measure_id="M2", ep_savings_kwh=1000.0, proxy_savings_kwh=10000.0
    )
    assert investigate["verdict"] == "investigate"
    assert "hint" in investigate

    keep = crosscheck_measure(
        measure_id="M3", ep_savings_kwh=-500.0, proxy_savings_kwh=10000.0
    )
    assert keep["verdict"] == "keep_iterating"

    missing = crosscheck_measure(measure_id="M4", ep_savings_kwh=None, proxy_savings_kwh=1.0)
    assert missing["verdict"] == "investigate"


def test_g14_gates_pass_and_fail():
    actual = [100.0] * 12
    good = g14_gates(actual, [101.0] * 12)
    assert good["calibrated"] is True
    bad = g14_gates(actual, [140.0] * 12)
    assert bad["calibrated"] is False
    assert bad["nmbe_pass"] is False


def _fake_savings_rows() -> list[dict]:
    return [
        {"step": 0, "measure_id": "baseline", "vs_previous": {}},
        {
            "step": 1,
            "measure_id": "SCHED-1",
            "vs_previous": {"kwh_saved": 9500.0, "therms_saved": 100.0},
        },
        {
            "step": 2,
            "measure_id": "GL36-1",
            "vs_previous": {"kwh_saved": 4000.0, "therms_saved": 0.0},
        },
    ]


def test_crosscheck_report_overall_verdict():
    proxies = {
        "SCHED-1": {"savings_kwh": 10000.0},
        "GL36-1": {"savings_kwh": 5000.0},
        "ORPHAN": {"savings_kwh": 1.0},
    }
    result = crosscheck_report(_fake_savings_rows(), proxies)
    assert result["overall_verdict"] == "in_line"
    assert result["unmatched_proxies"] == ["ORPHAN"]
    by_id = {m["measure_id"]: m for m in result["measures"]}
    assert by_id["SCHED-1"]["agreement_ratio"] == pytest.approx(0.95)
    assert by_id["GL36-1"]["agreement_ratio"] == pytest.approx(0.8)


def test_crosscheck_from_report_with_bills_and_cli(tmp_path):
    report = {
        "savings_by_measure": _fake_savings_rows(),
        "result_records": [
            {
                "measure_id": None,
                "monthly": [{"month": m, "electricity_kwh": 100.0} for m in range(1, 13)],
            }
        ],
    }
    proxies = {"SCHED-1": {"savings_kwh": 10000.0}, "GL36-1": {"savings_kwh": 5000.0}}
    bills = [102.0] * 12

    result = crosscheck_from_report(report, proxies, bills_monthly_kwh=bills)
    assert result["overall_verdict"] == "in_line"
    assert result["g14"]["calibrated"] is True

    report_path = tmp_path / "wattlab_report.json"
    proxies_path = tmp_path / "proxies.json"
    bills_path = tmp_path / "bills.json"
    out_path = tmp_path / "crosscheck.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    proxies_path.write_text(json.dumps(proxies), encoding="utf-8")
    bills_path.write_text(json.dumps(bills), encoding="utf-8")

    rc = crosscheck_main([
        "--report", str(report_path),
        "--proxies", str(proxies_path),
        "--bills", str(bills_path),
        "--out", str(out_path),
    ])
    assert rc == 0
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved["overall_verdict"] == "in_line"
