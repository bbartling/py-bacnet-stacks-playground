"""Hand fixtures for quarter-hour energy / peak math."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from energy_math import (  # noqa: E402
    hourly_mean_from_quarters,
    peak_kw,
    quarter_hour_kwh,
)


def test_flat_100kw_96_quarters_is_2400_kwh():
    kw = [100.0] * 96
    assert quarter_hour_kwh(kw) == pytest.approx(2400.0)
    assert peak_kw(kw) == pytest.approx(100.0)


def test_single_quarter_200kw_spike():
    kw = [0.0] * 96
    kw[12] = 200.0  # one quarter-hour
    assert quarter_hour_kwh(kw) == pytest.approx(50.0)  # 200 * 0.25
    assert peak_kw(kw) == pytest.approx(200.0)


def test_hourly_mean_energy_preserving_and_tod_boundaries():
    # Hour 0 (steps 0–3): 10 kW; hour 7 (steps 28–31): 40 kW; rest 0
    kw = [0.0] * 96
    for i in range(4):
        kw[i] = 10.0
    for i in range(28, 32):
        kw[i] = 40.0
    hourly = hourly_mean_from_quarters(kw)
    assert len(hourly) == 24
    assert hourly[0] == pytest.approx(10.0)
    assert hourly[7] == pytest.approx(40.0)
    assert hourly[1] == pytest.approx(0.0)
    # Energy: quarter path vs hourly means * 1 h
    assert quarter_hour_kwh(kw) == pytest.approx(sum(hourly))
    # TOD: step 0 = first interval of HE0; step 95 last of HE23
    assert peak_kw(kw) == pytest.approx(40.0)


def test_hourly_mean_rejects_wrong_length():
    with pytest.raises(ValueError, match="96"):
        hourly_mean_from_quarters([1.0] * 24)
