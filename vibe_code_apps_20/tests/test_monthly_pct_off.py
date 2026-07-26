"""Monthly model-vs-bills percent-off narratives."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.studio.monthly_pct_off import (
    build_monthly_pct_off,
    format_fuel_narrative,
    load_per_month_from_run,
    month_short_label,
    pct_off,
)


def test_pct_off_sign():
    assert pct_off(148.0, 100.0) == 48.0  # model too high
    assert abs(pct_off(82.0, 100.0) - (-18.0)) < 1e-9  # model too low
    assert pct_off(100.0, 0.0) is None


def test_month_short_label():
    assert month_short_label("2024-12") == "Dec"
    assert month_short_label("1") == "Jan"
    assert month_short_label("06") == "Jun"


def test_gas_and_elec_narratives():
    rows = [
        {"month": "2024-12", "observed_therms": 100, "simulated_therms": 148},
        {"month": "2024-01", "observed_therms": 100, "simulated_therms": 141},
        {"month": "2024-08", "observed_therms": 100, "simulated_therms": 172},
        {"month": "2024-10", "observed_therms": 100, "simulated_therms": 227},
        {"month": "2024-11", "observed_therms": 100, "simulated_therms": 144},
        {"month": "2024-02", "observed_therms": 100, "simulated_therms": 82},
        {"month": "2024-03", "observed_therms": 100, "simulated_therms": 77},
        {"month": "2024-04", "observed_therms": 100, "simulated_therms": 75},
        {"month": "2024-05", "observed_therms": 100, "simulated_therms": 77},
        {"month": "2024-06", "observed_therms": 100, "simulated_therms": 51},
        {"month": "2024-07", "observed_therms": 100, "simulated_therms": 69},
        {"month": "2024-09", "observed_therms": 100, "simulated_therms": 94},
        {"month": "2024-12", "observed_kwh": 100, "simulated_kwh": 135},
        {"month": "2024-04", "observed_kwh": 100, "simulated_kwh": 116},
        {"month": "2024-06", "observed_kwh": 100, "simulated_kwh": 117},
        {"month": "2024-01", "observed_kwh": 100, "simulated_kwh": 105},
        {"month": "2024-02", "observed_kwh": 100, "simulated_kwh": 98},
        {"month": "2024-03", "observed_kwh": 100, "simulated_kwh": 102},
        {"month": "2024-05", "observed_kwh": 100, "simulated_kwh": 101},
        {"month": "2024-07", "observed_kwh": 100, "simulated_kwh": 99},
        {"month": "2024-08", "observed_kwh": 100, "simulated_kwh": 103},
        {"month": "2024-09", "observed_kwh": 100, "simulated_kwh": 100},
        {"month": "2024-10", "observed_kwh": 100, "simulated_kwh": 104},
        {"month": "2024-11", "observed_kwh": 100, "simulated_kwh": 97},
    ]
    # Merge same-month elec+gas into combined rows like a real scorecard
    by_m: dict[str, dict] = {}
    for r in rows:
        m = r["month"]
        by_m.setdefault(m, {"month": m}).update(r)
    merged = list(by_m.values())

    analysis = build_monthly_pct_off(merged, ok_band_pct=15.0)
    assert analysis["has_data"]
    gas_txt = analysis["gas_narrative"]
    assert "Gas over" in gas_txt
    assert "Dec" in gas_txt and "+48%" in gas_txt
    assert "Gas under" in gas_txt
    assert "Feb" in gas_txt
    assert "OK-ish" in gas_txt or "Sep" in gas_txt

    elec_txt = analysis["elec_narrative"]
    assert "Elec" in elec_txt
    assert "Dec" in elec_txt
    # Mostly-within phrasing when only a few outliers
    assert "mostly within" in elec_txt.lower() or "over" in elec_txt.lower()


def test_load_per_month_from_run(tmp_path: Path):
    run = tmp_path / "run_a"
    run.mkdir()
    (run / "calibration_scorecard.json").write_text(
        json.dumps(
            {
                "utility_bills": {
                    "per_month": [
                        {
                            "month": "2024-01",
                            "observed_kwh": 100,
                            "simulated_kwh": 110,
                            "observed_therms": 50,
                            "simulated_therms": 40,
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    rows = load_per_month_from_run(run)
    assert len(rows) == 1
    assert rows[0]["modeled_kwh"] == 110
    analysis = build_monthly_pct_off(rows)
    assert analysis["elec"]["n"] == 1
    assert analysis["gas"]["n"] == 1


def test_format_empty():
    empty = {"n": 0, "over": [], "under": [], "ok": [], "ok_band_pct": 15}
    assert "no monthly" in format_fuel_narrative(empty, label="Gas").lower()


def test_gas_only_scorecard_elec_n_zero():
    """G14 can still show elec aggregates while per_month lacks kWh pairs."""
    rows = [
        {"month": "2024-01", "observed_therms": 100, "modeled_therms": 110},
        {"month": "2024-07", "observed_therms": 50, "modeled_therms": 40},
        {"month": "2024-12", "observed_therms": 100, "modeled_therms": 130},
    ]
    analysis = build_monthly_pct_off(rows)
    assert analysis["has_data"]
    assert analysis["gas"]["n"] == 3
    assert analysis["elec"]["n"] == 0
    assert "Gas" in (analysis["gas_narrative"] or "")
    assert analysis["elec_narrative"]  # still a "no monthly" style line from format


def test_fuel_filter_both_vs_elec_only_counts():
    rows = [
        {
            "month": "2024-01",
            "observed_kwh": 100,
            "modeled_kwh": 120,
            "observed_therms": 50,
            "modeled_therms": 40,
        },
        {
            "month": "2024-07",
            "observed_kwh": 100,
            "modeled_kwh": 90,
            "observed_therms": 20,
            "modeled_therms": 20,
        },
    ]
    a = build_monthly_pct_off(rows)
    assert a["elec"]["n"] == 2
    assert a["gas"]["n"] == 2
    # Panel is Streamlit-only; filter semantics match analyze counts above
    assert a["elec"]["over"] or a["elec"]["under"] or a["elec"]["ok"]
