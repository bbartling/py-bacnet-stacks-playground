"""EPW parse matrix over installed WeatherData + synthetic CI fixture."""
from __future__ import annotations

from pathlib import Path

import pytest

from vibe23.studio.uploads import parse_epw_day, parse_epw_path

DATA = Path(__file__).resolve().parent / "data"
EPLUS_WEATHER = Path(r"C:\EnergyPlusV26-1-0\WeatherData")
HAS_WEATHER = EPLUS_WEATHER.is_dir()

EPW_NAMES = [
    "USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw",
    "USA_CO_Golden-NREL.724666_TMY3.epw",
    "USA_FL_Tampa.Intl.AP.722110_TMY3.epw",
    "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
    "USA_VA_Sterling-Washington.Dulles.Intl.AP.724030_TMY3.epw",
]


@pytest.mark.parametrize(("month", "day"), [(7, 15), (1, 3)])
def test_synthetic_epw_days(month: int, day: int) -> None:
    outdoor = parse_epw_path(DATA / "synthetic_day.epw", month=month, day=day)
    assert len(outdoor.drybulb_f) == 24
    assert len(outdoor.drybulb_c) == 24
    assert all(-40.0 <= t <= 130.0 for t in outdoor.drybulb_f)


def test_synthetic_epw_missing_day_raises() -> None:
    with pytest.raises(ValueError, match="missing hourly dry-bulb"):
        parse_epw_path(DATA / "synthetic_day.epw", month=2, day=29)


@pytest.mark.skipif(not HAS_WEATHER, reason="EnergyPlus WeatherData not installed")
@pytest.mark.parametrize("name", EPW_NAMES)
@pytest.mark.parametrize(("month", "day"), [(7, 15), (1, 3)])
def test_installed_epw_matrix(name: str, month: int, day: int) -> None:
    path = EPLUS_WEATHER / name
    assert path.is_file(), path
    outdoor = parse_epw_day(
        path.read_text(encoding="utf-8", errors="replace"),
        month=month,
        day=day,
        source_name=name,
    )
    assert len(outdoor.drybulb_f) == 24
    assert all(-60.0 <= t <= 140.0 for t in outdoor.drybulb_f)
