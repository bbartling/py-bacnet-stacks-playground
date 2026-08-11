"""DSM console helpers (lookup / live routing + KPIs)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.lookup_emulator import STEPS
from eplus_gym_app.dsm_console import dsm_kpis, resolve_dsm_mode, run_dsm_lookup


def _w2a_farm(site: Path, day: str = "2026-01-26") -> None:
    farm = site / "eplus" / "dsm_farm_w2a"
    farm.mkdir(parents=True)
    rows = []
    for sid, base in (("baseline", 200.0), ("deep_setback", 160.0)):
        for q in range(STEPS):
            rows.append(
                {
                    "day": day,
                    "strategy_id": sid,
                    "quarter_index": q,
                    "facility_kw": base + 0.2 * q,
                    "oat_f": 8.0,
                }
            )
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_w2a_15min_v1.parquet", index=False)


def test_resolve_lookup_when_w2a_farm_exists(tmp_path: Path):
    _w2a_farm(tmp_path)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "lookup"
    assert "farm" in reason.lower()


def test_resolve_error_without_farm_or_live(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("eplus_gym_app.dsm_console.energyplus_available", lambda: False)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "error"
    assert "IdealLoads" in reason


def test_dsm_kpis_vs_baseline_and_actual():
    df = pd.DataFrame({"facility_kw": [100.0, 200.0, 150.0]})
    kpis = dsm_kpis(
        df,
        {"honesty": "W2A_PHYSICAL_DSM", "provenance": "FARM_LOOKUP_EMULATOR", "promote": False},
        actual_peak_kw=220.0,
        baseline_peak_kw=250.0,
    )
    assert kpis["peak_kw"] == pytest.approx(200.0)
    assert kpis["kwh"] == pytest.approx((100 + 200 + 150) * 0.25)
    assert kpis["vs_actual_pct"] == pytest.approx((200 - 220) / 220 * 100)
    assert kpis["vs_baseline_pct"] == pytest.approx((200 - 250) / 250 * 100)
    assert kpis["promote"] is False


def test_run_dsm_lookup_returns_frame(tmp_path: Path):
    _w2a_farm(tmp_path)
    pack = run_dsm_lookup(
        site_root=tmp_path,
        strategy_id="deep_setback",
        day="2026-01-26",
    )
    assert pack["meta"]["family"] == "w2a"
    assert pack["meta"]["honesty"] == "W2A_PHYSICAL_DSM"
    assert not pack["frame"].empty
    assert pack["kpis"]["peak_kw"] < 220
