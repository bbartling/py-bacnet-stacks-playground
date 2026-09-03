"""Studio parsers, IDF dashboard, and fixture smoke tests."""
from __future__ import annotations

from pathlib import Path

from vibe23.envfile import parse_env_file
from vibe23.residential.constants import DT_HOURS
from vibe23.residential.model import MODEL_IDF
from vibe23.studio.demo_data import (
    DEMO_FLOOR_FT2,
    daily_kwh,
    hourly_cost,
    hourly_kwh,
    load_outdoor_day,
    load_season_day,
    run_battery_on_load,
)
from vibe23.studio.idf_geometry import idf_massing_figure, parse_idf_geometry
from vibe23.studio.idf_inspect import inspect_idf
from vibe23.studio.uploads import expand_tariff_to_288, parse_epw_day, parse_tariff_csv


def test_parse_residential_idf_massing() -> None:
    geom = parse_idf_geometry(MODEL_IDF)
    assert geom.surfaces
    assert "ZONE ONE" in geom.zone_names
    fig = idf_massing_figure(geom, zone_temps={"ZONE ONE": 22.5}, title="test")
    assert fig.data


def test_idf_dashboard_metrics() -> None:
    dash = inspect_idf(MODEL_IDF)
    assert dash.envelope.floor_ft2 > 3000
    assert dash.simulation_control.zone_sizing is False
    assert dash.cooling_tons is not None and dash.cooling_tons > 4
    assert dash.heating_capacity_w is not None
    assert dash.hvac_autosize is True  # fan power AUTOSIZE present
    assert dash.version is not None


def test_summer_and_winter_extreme_fixtures() -> None:
    summer = load_season_day("summer")
    winter = load_season_day("winter")
    assert len(summer["baseline_kw"]) == 288
    assert len(winter["baseline_kw"]) == 288
    assert abs(float(summer["dt_hours"]) - DT_HOURS) < 1e-9
    s_kwh = daily_kwh(list(summer["baseline_kw"]))
    w_kwh = daily_kwh(list(winter["baseline_kw"]))
    assert 90.0 <= s_kwh <= 130.0
    assert 60.0 <= w_kwh <= 130.0
    assert DEMO_FLOOR_FT2 > 3000
    out_s = load_outdoor_day(season="summer")
    out_w = load_outdoor_day(season="winter")
    assert len(out_s["drybulb_f"]) == 24
    assert len(out_w["drybulb_f"]) == 24
    assert max(out_s["drybulb_f"]) > max(out_w["drybulb_f"])


def test_hourly_kwh_and_cost() -> None:
    day = load_season_day("summer")
    kw = list(day["baseline_kw"])
    hk = hourly_kwh(kw)
    assert len(hk) == 24
    assert abs(sum(hk) - daily_kwh(kw)) < 1e-6
    rates = [0.1] * 288
    hc = hourly_cost(kw, rates)
    assert len(hc) == 24
    assert abs(sum(hc) - daily_kwh(kw) * 0.1) < 1e-6


def test_epw_and_tariff_parsers(tmp_path: Path) -> None:
    epw = Path(r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw")
    if epw.is_file():
        outdoor = parse_epw_day(epw.read_text(encoding="utf-8", errors="replace"), month=7, day=15)
        assert outdoor.drybulb_f[12] > 70
    csv_text = "hour,rate_usd_per_kwh\n" + "\n".join(f"{h},{0.1 + 0.01 * h}" for h in range(24))
    upload = parse_tariff_csv(csv_text)
    assert upload.intervals == 24
    assert len(expand_tariff_to_288(upload)) == 288
    env = tmp_path / ".env"
    env.write_text("ENERGYPLUS_EXE=/usr/local/EnergyPlus-26-1-0/energyplus\n", encoding="utf-8")
    parsed = parse_env_file(env)
    assert parsed["ENERGYPLUS_EXE"].endswith("energyplus")


def test_summer_battery_dispatch() -> None:
    day = load_season_day("summer")
    out = run_battery_on_load(list(day["baseline_kw"]), capacity_kwh=13.5, max_power_kw=5.0)
    assert out["billing_cost"] < out["baseline_billing_cost"]
