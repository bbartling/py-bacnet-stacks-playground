"""Tests for the public controls-retrofit benchmark bands and the new
ESCO proxy registrations (chw_reset / condenser_water_reset /
pneumatic_compressor)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wattlab.bench.registry import get
from wattlab.bench import runner  # noqa: F401  (registers algorithms + esco)
from wattlab.benchmarks.controls_retrofit import (
    CONFIDENCE_LEVELS,
    SOURCE_KINDS,
    check_savings_pct,
    is_placeholder,
    list_classes,
    load_benchmarks,
    lookup_class,
)
from wattlab.weather.bins import washington_dc_noaa


# ---------------------------------------------------------------------------
# Benchmark data integrity
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "retrofit_class",
    "label",
    "savings_basis",
    "lo_pct",
    "typical_pct",
    "hi_pct",
    "confidence",
    "applicability",
    "sources",
}


def test_every_class_has_required_fields_and_sane_band():
    rows = load_benchmarks()
    assert rows, "bundled controls_retrofit_public.json must not be empty"
    for row in rows:
        missing = REQUIRED_FIELDS - set(row)
        assert not missing, f"{row.get('retrofit_class')} missing {missing}"
        assert 0 <= row["lo_pct"] <= row["typical_pct"] <= row["hi_pct"] <= 100
        assert row["confidence"] in CONFIDENCE_LEVELS


def test_sources_are_public_reports_or_honest_placeholders():
    for row in load_benchmarks():
        assert row["sources"], f"{row['retrofit_class']} has no sources"
        for src in row["sources"]:
            assert src["kind"] in SOURCE_KINDS
            if src["kind"] == "public_report":
                assert src.get("url"), f"{row['retrofit_class']} public_report needs a URL"
        # A band resting on any placeholder must never claim high confidence.
        if is_placeholder(row):
            assert row["confidence"] == "low", (
                f"{row['retrofit_class']} uses a screening placeholder but "
                f"claims confidence={row['confidence']}"
            )


def test_expected_retrofit_classes_present():
    classes = list_classes()
    assert classes == sorted(classes)
    for expected in (
        "scheduling_occupancy",
        "chw_reset",
        "condenser_water_reset",
        "pneumatic_to_ddc_conversion",
        "guideline36_airside_package",
    ):
        assert expected in classes


def test_lookup_class_and_extra_paths(tmp_path: Path):
    assert lookup_class("no_such_class") is None
    entry = lookup_class("scheduling_occupancy")
    assert entry and entry["savings_basis"] == "whole_building_energy_pct"

    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps({"classes": [{"retrofit_class": "custom_class", "lo_pct": 1,
                                 "typical_pct": 2, "hi_pct": 3}]}),
        encoding="utf-8",
    )
    rows = load_benchmarks([extra])
    assert lookup_class("custom_class", rows) is not None


def test_check_savings_pct_bands():
    within = check_savings_pct(retrofit_class="scheduling_occupancy", savings_pct=8.0)
    assert within["band"] == "within_band"
    assert within["screening_placeholder"] is False

    above = check_savings_pct(retrofit_class="scheduling_occupancy", savings_pct=45.0)
    assert above["band"] == "above_band"

    below = check_savings_pct(retrofit_class="scheduling_occupancy", savings_pct=0.5)
    assert below["band"] == "below_band"

    unknown = check_savings_pct(retrofit_class="warp_drive", savings_pct=10.0)
    assert unknown["band"] == "no_reference"

    cw = check_savings_pct(retrofit_class="condenser_water_reset", savings_pct=3.0)
    assert cw["screening_placeholder"] is True
    assert cw["confidence"] == "low"


# ---------------------------------------------------------------------------
# New ESCO proxy registrations
# ---------------------------------------------------------------------------

_HYDRONIC_INPUTS = {
    "capacity_mbh": 1200.0,
    "kw_per_ton": 0.9,
    "on_point_f": 55.0,
    "design_temp_f": 95.0,
    "max_savings_fraction": 0.05,
    "n_reset_bins": 5,
    "schedule": {"shifts": [8, 8, 8], "days_per_week": 7},
    "bins": washington_dc_noaa(),
}


def test_chw_reset_wraps_hydronic_chilled_water_mode():
    wrapped = get("chw_reset")(dict(_HYDRONIC_INPUTS))
    direct = get("hydronic_reset_bins")({**_HYDRONIC_INPUTS, "mode": "chilled_water"})
    assert wrapped["mode"] == "chilled_water"
    assert wrapped["savings_kwh"] == pytest.approx(direct["savings_kwh"])
    assert wrapped["savings_kwh"] > 0


def test_condenser_water_reset_is_gentler_screening_proxy():
    cw = get("condenser_water_reset")(dict(_HYDRONIC_INPUTS))
    assert cw["mode"] == "condenser_water"
    assert "tower fan" in cw["note"]
    # Same ladder shape via explicit max_savings_fraction override.
    explicit = get("hydronic_reset_bins")({**_HYDRONIC_INPUTS, "mode": "chilled_water"})
    assert cw["savings_kwh"] == pytest.approx(explicit["savings_kwh"])
    # Default ladder (no max_savings_fraction supplied) is gentler than CHW's.
    defaults = {k: v for k, v in _HYDRONIC_INPUTS.items() if k != "max_savings_fraction"}
    assert (
        get("condenser_water_reset")(defaults)["savings_kwh"]
        < get("chw_reset")(defaults)["savings_kwh"]
    )


def test_pneumatic_compressor_savings_math():
    out = get("pneumatic_compressor")({
        "compressor_kw": 7.5,
        "baseline_annual_hours": 8760.0,
        "proposed_annual_hours": 0.0,
        "load_factor": 0.4,
    })
    assert out["savings_kwh"] == pytest.approx(7.5 * 0.4 * 8760.0)
    assert out["proposed_kwh"] == pytest.approx(0.0)

    partial = get("pneumatic_compressor")({
        "compressor_kw": 7.5,
        "baseline_annual_hours": 8760.0,
        "proposed_annual_hours": 2000.0,
    })
    assert partial["avoided_hours"] == pytest.approx(6760.0)
    assert partial["savings_kwh"] == pytest.approx(7.5 * 0.5 * 6760.0)

    with pytest.raises(ValueError):
        get("pneumatic_compressor")({
            "compressor_kw": 0.0, "baseline_annual_hours": 100.0,
        })
