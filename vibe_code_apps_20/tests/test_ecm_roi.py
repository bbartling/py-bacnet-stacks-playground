"""Per-ECM ROI $/ft² × coverage calculator."""

from __future__ import annotations

from wattlab.studio.ecm_roi import (
    implementation_cost_usd,
    seed_roi_cost_rows,
)


def test_liberty_style_partial_ddc_g36_coverage() -> None:
    """50% of 140k ft² at $6/ft² → $420k for G36 airside DDC path."""
    cost = implementation_cost_usd(
        floor_area_ft2=140_000.0,
        usd_per_ft2=6.0,
        coverage_fraction=0.50,
    )
    assert cost == 420_000.0


def test_fixed_usd_overrides_ft2_math() -> None:
    cost = implementation_cost_usd(
        floor_area_ft2=140_000.0,
        usd_per_ft2=6.0,
        coverage_fraction=0.50,
        fixed_usd=250_000.0,
    )
    assert cost == 250_000.0


def test_seed_roi_preserves_engineer_edits() -> None:
    rows = seed_roi_cost_rows(
        ["ECM-GL36-AIRSIDE", "ECM-AHU-SCHED-ALIGN"],
        floor_area_ft2=100_000.0,
        existing={
            "ECM-GL36-AIRSIDE": {
                "usd_per_ft2": 7.5,
                "coverage_fraction": 0.4,
                "note": "Liberty Bldg 100",
            }
        },
    )
    by_id = {r["measure_id"]: r for r in rows}
    assert by_id["ECM-GL36-AIRSIDE"]["usd_per_ft2"] == 7.5
    assert by_id["ECM-GL36-AIRSIDE"]["coverage_fraction"] == 0.4
    assert by_id["ECM-GL36-AIRSIDE"]["implementation_cost_usd"] == 300_000.0
    assert by_id["ECM-AHU-SCHED-ALIGN"]["coverage_fraction"] == 1.0
