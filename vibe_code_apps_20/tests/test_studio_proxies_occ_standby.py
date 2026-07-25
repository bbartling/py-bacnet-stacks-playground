"""Regression tests for the occupied-standby plus DCV Studio proxy."""

from __future__ import annotations

from wattlab.studio.proxies import estimate_proxy_savings


def test_occ_standby_dcv_sums_unoccupied_oad_and_dcv_with_provenance() -> None:
    savings = estimate_proxy_savings(
        {"floor_area_ft2": 50_000},
        ["ECM-OCC-STANDBY-DCV", "ECM-DCV-CO2"],
    )

    composite = savings["ECM-OCC-STANDBY-DCV"]
    dcv_only = savings["ECM-DCV-CO2"]

    assert composite["calculators"] == ["oad_unoccupied_closed", "dcv_bins"]
    assert dcv_only["calculators"] == ["dcv_bins"]
    assert composite["savings_kwh"] > dcv_only["savings_kwh"]
    assert composite["savings_therms"] > dcv_only["savings_therms"]
