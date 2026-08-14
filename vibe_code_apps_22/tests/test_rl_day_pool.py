"""Unique EPW day pool (no EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

from eplus_gym.rl.day_pool import sample_unique_heating_days, unique_dates_from_epw


def _tiny_epw(path: Path) -> None:
    # LOCATION header + 5 unique days (Jan + Oct + Jul)
    rows = ["LOCATION,Test"]
    for y, m, d in (
        (2026, 1, 20),
        (2026, 1, 21),
        (2026, 10, 5),
        (2026, 7, 4),
        (2026, 4, 2),
    ):
        for h in range(1, 25):
            rows.append(f"{y},{m},{d},{h},0,?,0.0")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_unique_dates_from_epw(tmp_path: Path):
    epw = tmp_path / "t.epw"
    _tiny_epw(epw)
    days = unique_dates_from_epw(epw)
    assert len(days) == 5


def test_sample_caps_at_available(tmp_path: Path):
    epw = tmp_path / "t.epw"
    _tiny_epw(epw)
    out = sample_unique_heating_days(epw, n=100, seed=0)
    assert out["n_available"] == 5
    assert out["n_selected"] == 5
    assert out["shortfall"] == 95
    assert "2026-01-20" in out["days"]
    assert "2026-07-04" in out["days"]  # remaining after heating/shoulder


def test_sample_heating_first(tmp_path: Path):
    epw = tmp_path / "t.epw"
    _tiny_epw(epw)
    out = sample_unique_heating_days(epw, n=2, seed=1)
    assert out["n_selected"] == 2
    assert set(out["days"]) <= {"2026-01-20", "2026-01-21"}
