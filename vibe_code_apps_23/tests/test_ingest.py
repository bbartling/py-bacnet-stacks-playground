import pandas as pd
import pytest

from vibe23.ingest import aggregate_power_kw, build_inventory, iter_csv_files


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


def test_inventory_ignores_macos_appledouble_and_hidden_extraction_artifacts(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "__MACOSX").mkdir()
    (tmp_path / ".partial").mkdir()
    for path in (
        tmp_path / "real" / "signal.csv",
        tmp_path / "real" / "._signal.csv",
        tmp_path / "__MACOSX" / "signal.csv",
        tmp_path / ".partial" / "signal.csv",
        tmp_path / ".hidden.csv",
    ):
        path.write_text("timestamp,power_kw\n2019-01-01,1\n", encoding="utf-8")

    assert [path.relative_to(tmp_path).as_posix() for path in iter_csv_files(tmp_path)] == ["real/signal.csv"]
    assert build_inventory(tmp_path)["path"].tolist() == ["real/signal.csv"]
