"""Weather preference / fallback and OAT-METEO both-required policy."""

from __future__ import annotations

import pandas as pd

from app.rules.cookbook_catalog import RULES_BY_ID
from app.rules.runner import merge_weather, run_cookbook_rule
from app.weather_resolver import (
    apply_effective_oat_columns,
    has_bas_oat,
    has_web_oat,
    inject_oa_t_for_physics,
    oat_meteo_availability,
    resolve_effective_oat,
)


def _idx(n: int = 6) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")


def test_effective_oat_prefers_web_when_both_present():
    idx = _idx()
    df = pd.DataFrame({"outside-air-temp": [50.0] * 6, "web-outside-air-temp": [40.0] * 6}, index=idx)
    out = apply_effective_oat_columns(df)
    assert has_bas_oat(out) and has_web_oat(out)
    assert out.attrs["oa_t_effective_source"] == "web"
    assert float(out["oa_t_effective"].iloc[0]) == 40.0
    # BAS preserved
    assert float(out["outside-air-temp"].iloc[0]) == 50.0
    assert float(out["bas-outside-air-temp"].iloc[0]) == 50.0


def test_effective_oat_falls_back_to_bas_when_web_missing():
    idx = _idx()
    df = pd.DataFrame({"outside-air-temp": [55.0] * 6}, index=idx)
    out = apply_effective_oat_columns(df)
    assert out.attrs["oa_t_effective_source"] == "bas"
    assert float(out["oa_t_effective"].iloc[0]) == 55.0


def test_merge_weather_adds_effective_before_roles():
    idx = _idx()
    df = pd.DataFrame({"discharge-air-temp": [55.0] * 6}, index=idx)
    wx = pd.DataFrame({"web-outside-air-temp": [42.0] * 6, "web-outside-air-humidity": [40.0] * 6}, index=idx)
    merged = merge_weather(df, wx)
    assert "oa_t_effective" in merged.columns
    assert merged.attrs["oa_t_effective_source"] == "web"
    injected = inject_oa_t_for_physics(merged)
    assert "outside-air-temp" in injected.columns
    assert float(injected["outside-air-temp"].iloc[0]) == 42.0


def test_oat_meteo_requires_both_sources():
    idx = _idx()
    web_only = apply_effective_oat_columns(pd.DataFrame({"web-outside-air-temp": [40.0] * 6}, index=idx))
    ok, missing = oat_meteo_availability(web_only)
    assert not ok
    assert any("bas" in m for m in missing)

    bas_only = apply_effective_oat_columns(pd.DataFrame({"outside-air-temp": [50.0] * 6}, index=idx))
    ok2, missing2 = oat_meteo_availability(bas_only)
    assert not ok2
    assert any("web-outside-air-temp" in m for m in missing2)

    both = apply_effective_oat_columns(
        pd.DataFrame({"outside-air-temp": [50.0] * 6, "web-outside-air-temp": [40.0] * 6}, index=idx)
    )
    ok3, missing3 = oat_meteo_availability(both)
    assert ok3 and not missing3


def test_oat_meteo_rule_skipped_without_bas():
    idx = _idx()
    df = pd.DataFrame({"web-outside-air-temp": [40.0] * 6}, index=idx)
    rule = RULES_BY_ID["OAT-METEO"]
    result = run_cookbook_rule(
        rule,
        df,
        equipment_id="AHU_1",
        equipment_kind="ahu",
        poll_seconds=300.0,
    )
    assert result.status == "SKIPPED_MISSING_ROLES"
    assert any("bas" in m.lower() for m in result.missing_roles)


def test_oat_meteo_runs_when_both_present():
    idx = _idx()
    df = pd.DataFrame({"outside-air-temp": [50.0] * 6, "web-outside-air-temp": [40.0] * 6}, index=idx)
    rule = RULES_BY_ID["OAT-METEO"]
    result = run_cookbook_rule(
        rule,
        df,
        equipment_id="AHU_1",
        equipment_kind="ahu",
        poll_seconds=300.0,
        params_by_rule={"OAT-METEO": {"oat_err": 5.0, "confirm_min": 0.0}},
    )
    assert result.status in {"PASS", "FAULT"}
    assert result.metrics.get("has_bas_oat") is True
    assert result.metrics.get("has_web_weather") is True


def test_resolve_effective_oat_from_weather_frame():
    idx = _idx()
    df = pd.DataFrame({"discharge-air-temp": [1.0] * 6}, index=idx)
    wx = pd.DataFrame({"web-outside-air-temp": [33.0] * 6}, index=idx)
    series, src = resolve_effective_oat(df, wx)
    assert src == "web"
    assert float(series.iloc[0]) == 33.0
