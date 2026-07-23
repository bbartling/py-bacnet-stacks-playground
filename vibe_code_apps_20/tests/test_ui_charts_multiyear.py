"""UI charts tip: EUI bullet, multi-year weather fit, month abbrevs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def test_month_abbrev():
    from wattlab.studio.eui_charts import MONTH_ABBREV, month_abbrev, month_abbrev_columns

    assert month_abbrev(1) == "Jan"
    assert month_abbrev("12") == "Dec"
    assert month_abbrev("07") == "Jul"
    mat = pd.DataFrame([[1.0] * 12], columns=list(range(1, 13)), index=[2024])
    renamed = month_abbrev_columns(mat)
    assert list(renamed.columns) == list(MONTH_ABBREV)


def test_eui_peer_bullet_figure_has_band_and_rows():
    from wattlab.studio.eui_charts import eui_peer_bullet_figure

    fig = eui_peer_bullet_figure(
        peer_p20=34.0,
        peer_p50=52.9,
        peer_p80=71.0,
        series=[
            {"label": "Bills (site)", "eui": 66.9, "color": "#1f77b4"},
            {"label": "Model (prototype)", "eui": 24.0, "color": "#d62728"},
        ],
        title="test",
        height=420,
    )
    # One upright rect + one p50 line per series row
    assert len(fig.layout.shapes) == 4
    assert any(t.mode and "markers" in str(t.mode) for t in fig.data)
    assert fig.layout.height >= 420
    # Y is EUI (upright); X is category labels
    assert fig.layout.yaxis.title.text and "EUI" in str(fig.layout.yaxis.title.text)


def test_fit_window_defaults_to_max_years():
    from wattlab.benchmarks.fuel_weather import (
        fit_window_choices,
        months_for_fit_years,
    )

    months = [f"{y}-{m:02d}" for y in range(2016, 2026) for m in range(1, 13)]
    # 10 full years
    assert len(months) == 120
    choices = fit_window_choices(months)
    assert choices["max_years"] == 10
    assert choices["default_years"] == 10
    assert months_for_fit_years(months, 10) == 120
    assert months_for_fit_years(months, 1) == 12
    assert months_for_fit_years(months, 3, use_all=True) == 120


def test_align_fuel_respects_months_window(tmp_path: Path):
    from wattlab.benchmarks.fuel_weather import align_fuel_and_degree_days
    from wattlab.benchmarks.meters import BuildingRef, Campus, Meter

    # 24 months of bills
    months = [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 13)]
    bills = pd.DataFrame({"month": months, "usage": [100.0 + i for i in range(24)]})
    b = BuildingRef(building_id="b1", label="B1", floor_area_ft2=10000.0, property_type="office")
    m = Meter(
        meter_id="g1",
        fuel="gas",
        unit="mcf",
        serves=["b1"],
        bills=bills,
    )
    campus = Campus(
        campus_id="c1",
        label="C",
        buildings=[b],
        meters=[m],
        lat=42.0,
        lon=-83.0,
    )
    # Hourly OAT covering both years
    idx = pd.date_range("2023-01-01", periods=24 * 30 * 24, freq="h")
    oat = pd.Series(
        35.0 + 30.0 * np.sin(np.arange(len(idx)) / 24 / 365 * 2 * np.pi),
        index=idx,
        name="dry_bulb_f",
    )
    aligned12, win12 = align_fuel_and_degree_days(campus, oat, months=12)
    aligned24, win24 = align_fuel_and_degree_days(campus, oat, months=24)
    assert len(win12) == 12
    assert len(win24) == 24
    assert len(win24) > len(win12)
    assert not aligned24.empty


def test_studio_apptest_fuel_twin_no_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from wattlab.studio.bootstrap import build_bootstrap_payload, write_bootstrap

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    (tmp_path / "reports").mkdir(parents=True)
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "floors": 6,
        "lat": 42.33,
        "lon": -83.04,
    }
    (tmp_path / "reports" / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    write_bootstrap(
        build_bootstrap_payload(
            preferred_run_id="noop",
            answers_path="reports/answers.json",
        )
    )
    root = Path(__file__).resolve().parents[1]
    at = AppTest.from_file(str(root / "studio.py"), default_timeout=60)
    at.run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Twin / calibrate").run()
    assert not at.exception
