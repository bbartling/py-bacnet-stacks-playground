import pandas as pd
import pytest

from vibe23.ingest import aggregate_power_kw


def test_aggregate_power_regular_15_minute_samples():
    index = pd.date_range("2019-01-01 00:00", periods=4, freq="15min")
    power = pd.Series([4.0, 4.0, 4.0, 4.0], index=index)
    out = aggregate_power_kw(power, "1h")
    assert out.iloc[0]["energy_kwh"] == pytest.approx(4.0)
    assert out.iloc[0]["peak_kw"] == pytest.approx(4.0)
    assert out.iloc[0]["samples"] == 4


def test_aggregate_power_fails_on_large_gap():
    index = pd.to_datetime(["2019-01-01 00:00", "2019-01-01 00:15", "2019-01-01 05:00"])
    power = pd.Series([1.0, 1.0, 1.0], index=index)
    with pytest.raises(ValueError, match="gap exceeds"):
        aggregate_power_kw(power, "1h")
