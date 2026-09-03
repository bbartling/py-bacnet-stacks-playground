from __future__ import annotations

from pathlib import Path

from vibe23.weather import FixtureForecastWeatherProvider, StaticEpwWeatherProvider, find_default_epw


def test_static_epw_provider_finds_denver_type():
    provider = StaticEpwWeatherProvider()
    info = provider.describe()
    # May be missing on CI without EnergyPlus; still must describe honestly
    assert info["provider"] == "StaticEpwWeatherProvider"
    epw = find_default_epw()
    if epw is not None:
        assert provider.epw_path() == epw


def test_fixture_forecast_provider(tmp_path: Path):
    path = tmp_path / "forecast.json"
    path.write_text(
        '{"day":"x","drybulb_c":[1,2,3],"claim":"ILLUSTRATIVE_FORECAST_FIXTURE"}',
        encoding="utf-8",
    )
    provider = FixtureForecastWeatherProvider(path)
    assert provider.drybulb_c() == [1.0, 2.0, 3.0]
    assert "ILLUSTRATIVE" in provider.describe()["claim"]
