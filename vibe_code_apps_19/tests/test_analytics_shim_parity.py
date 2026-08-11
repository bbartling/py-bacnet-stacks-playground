"""Local app analytics modules must be thin OpenFDD shims."""

from __future__ import annotations

import app.metering as metering
import app.occupancy as occupancy
import app.rcx_plots as rcx_plots
import open_fdd.analytics.metering as of_metering
import open_fdd.analytics.occupancy as of_occupancy
import open_fdd.analytics.rcx_plots as of_rcx


def test_occupancy_is_package_module():
    assert occupancy.OccupancySchedule is of_occupancy.OccupancySchedule
    assert occupancy.occupied_mask is of_occupancy.occupied_mask


def test_metering_is_package_module():
    assert metering.build_meter_monthly_table is of_metering.build_meter_monthly_table


def test_rcx_plots_is_package_module():
    assert rcx_plots.zone_comfort_fail_ranking is of_rcx.zone_comfort_fail_ranking
    assert "zone_comfort_rank" in {p.id for p in rcx_plots.PRESETS}
