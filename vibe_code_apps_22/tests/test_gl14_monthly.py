"""Published A04 monthly bills vs eplusmtr."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_gym_app.gl14_monthly import (
    champion_gl14_monthly,
    load_observed_monthly,
    monthly_sim_from_mtr,
)


def test_monthly_sim_from_mtr_skips_partial(tmp_path: Path):
    sim = tmp_path / "sim"
    sim.mkdir()
    (sim / "eplusmtr.csv").write_text(
        "\n".join(
            [
                "Date/Time,Electricity:Facility [J](Hourly),Electricity:Facility [J](Monthly)",
                " 01/21  24:00:00,3600000,15174778820",
                " 01/31  08:00:00,720000000,",
                " 01/31  24:00:00,3600000,288181687939",
                " 08/31  24:00:00,3600000,120055526008",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    df = monthly_sim_from_mtr(sim, peak_day="2026-01-26")
    assert list(df["month"]) == ["2025-08", "2026-01"]
    jan = df.loc[df["month"] == "2026-01"].iloc[0]
    assert jan["kwh_sim"] == pytest.approx(288181687939 / 3_600_000.0)
    assert jan["peak_kw_sim"] == pytest.approx(200.0)


def test_monthly_sim_from_mtr_gas(tmp_path: Path):
    sim = tmp_path / "sim"
    sim.mkdir()
    (sim / "eplusmtr.csv").write_text(
        "Date/Time,NaturalGas:Facility [J](Monthly),NaturalGas:Facility [J](Hourly)\n"
        " 01/31  24:00:00,3600000000,7200000\n",
        encoding="utf-8",
    )
    df = monthly_sim_from_mtr(sim, peak_day="2026-01-26", fuel="gas")
    assert list(df["month"]) == ["2026-01"]
    assert df.iloc[0]["kwh_sim"] == pytest.approx(3600000000 / 3_600_000.0)


def test_join_bills_to_sim(tmp_path: Path):
    reports = tmp_path / "reports" / "eplus"
    reports.mkdir(parents=True)
    pd.DataFrame(
        [
            {"month": "2026-01", "kwh_obs": 81491.0, "peak_kw_obs": 284.82},
            {"month": "2025-08", "kwh_obs": 32789.0, "peak_kw_obs": 299.4},
        ]
    ).to_csv(reports / "observed_monthly_utility.csv", index=False)
    obs = load_observed_monthly(tmp_path)
    assert set(obs["month"]) == {"2026-01", "2025-08"}

    sim = tmp_path / "sim"
    sim.mkdir()
    (sim / "eplusmtr.csv").write_text(
        "Date/Time,Electricity:Facility [J](Hourly),Electricity:Facility [J](Monthly)\n"
        " 01/31  24:00:00,3600000,288000000000\n"
        " 08/31  24:00:00,3600000,120000000000\n",
        encoding="utf-8",
    )

    class _Pin:
        id = "A04"
        sim_dir = sim

    class _Active:
        id = "A04"
        family = "W2A_PHYSICAL_DSM"
        dial_id = "A04"

    class _Ladder:
        peak_day = "2026-01-26"
        models = (_Pin(),)

    class _Bundle:
        site = tmp_path
        dial_ladder = _Ladder()

    pairs = champion_gl14_monthly(_Bundle(), _Active())  # type: ignore[arg-type]
    jan = pairs.loc[pairs["month"] == "2026-01"].iloc[0]
    assert jan["kwh_obs"] == 81491.0
    assert abs(jan["kwh_sim"] - 80000.0) < 1.0
    assert jan["pct_error"] < 0
