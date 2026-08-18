"""Campaign bundle: contiguous dates, forecasts required, A04 refused."""
from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.rl.campaign_bundle import (
    CampaignBundleError,
    empty_bundle_template,
    prepare_campaign_bundle,
    refuse_a04_unless_explicit,
)


def test_contiguous_template_ok():
    body = empty_bundle_template(days=["2025-12-08", "2025-12-09", "2025-12-10"])
    assert body["days"][0] == "2025-12-08"
    assert body["forecast_source"] == "PERFECT_EPISODE_FORECAST"
    assert body["split"]["train"]


def test_isolated_dates_refused():
    with pytest.raises(CampaignBundleError, match="contiguous"):
        empty_bundle_template(days=["2025-12-08", "2025-12-10"])


def test_a04_refused_when_trackb_is_active():
    with pytest.raises(CampaignBundleError, match="refuses A04"):
        refuse_a04_unless_explicit(idf_name=A04_IDF_NAME, manifest={"a04_explicitly_verified_active": False})


def test_prepare_requires_forecasts_and_baselines(tmp_path):
    idf = tmp_path / "trackb_child.idf"
    idf.write_text("Version, 26.1;", encoding="utf-8")
    epw = tmp_path / "x.epw"
    epw.write_text("LOCATION,x\n", encoding="utf-8")
    manifest = {
        "idf_path": str(idf),
        "idf_sha256": "unused",
        "a04_explicitly_verified_active": False,
        "model_id": "trackb_test",
    }
    with pytest.raises(CampaignBundleError, match="forecast"):
        prepare_campaign_bundle(
            app_root=tmp_path,
            days=["2025-12-08", "2025-12-09"],
            hourly_forecasts={"2025-12-08": [-1.0] * 24},
            paired_baselines={},
            idf=idf,
            epw=epw,
            manifest=manifest,
        )


def test_prepare_ok_with_supplied_forecasts_and_baselines(tmp_path):
    idf = tmp_path / "trackb_child.idf"
    idf.write_text("Version, 26.1;", encoding="utf-8")
    epw = tmp_path / "x.epw"
    epw.write_text("LOCATION,x\n", encoding="utf-8")
    days = ["2025-12-08", "2025-12-09"]
    forecasts = {d: [-4.0] * 24 for d in days}
    baselines = {
        d: {
            "facility_kw": [10.0] * 96,
            "zone_temps_series_f": {f"z{i}": [70.0] * 96 for i in range(6)},
            "n_intervals": 96,
        }
        for d in days
    }
    bundle = prepare_campaign_bundle(
        app_root=tmp_path,
        days=days,
        hourly_forecasts=forecasts,
        paired_baselines=baselines,
        idf=idf,
        epw=epw,
        manifest={"idf_path": str(idf), "model_id": "trackb_test"},
    )
    assert bundle["idf_sha256"]
    assert bundle["forecast_source"] == "PERFECT_EPISODE_FORECAST"
    assert set(bundle["hourly_forecasts"]) == set(days)
