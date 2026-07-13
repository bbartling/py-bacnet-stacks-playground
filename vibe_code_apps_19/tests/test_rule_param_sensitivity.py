"""Param sensitivity: declared sliders (except confirm_min) must change the raw fault mask.

Never subtract the same tol from both sides of an inequality (dead slider).
Plotly downsample is not data smoothing — rule math never smooths historian data.
"""
from __future__ import annotations

import inspect
import re
from typing import Any

import pandas as pd

from app.rules.cookbook_catalog import RULES_BY_ID, fc2, fc3, fc5
from app.rules import run_rule


def _ts_df(n: int, *, equipment_id: str = "AHU_1", **cols: Any) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    data = {k: ([v] * n if not isinstance(v, list) else v) for k, v in cols.items()}
    df = pd.DataFrame(data, index=idx)
    df.attrs["equipment_id"] = equipment_id
    df.attrs["equipment_type"] = "AHU"
    return df


def _status(rule_id: str, df: pd.DataFrame, **params: Any) -> str:
    payload = {
        "confirm_min": 0,
        **params,
    }
    return run_rule(
        rule_id,
        df,
        payload,
        poll_seconds=300.0,
        require_operational_gates=False,
    ).status


def test_fc2_mix_tol_widens_envelope() -> None:
    """mat between min(rat,oat) and min-2*tol_loose: tight FAULT, loose PASS."""
    df = _ts_df(24, mat=48.0, oa_t=50.0, rat=70.0, fan_cmd=50.0)
    assert _status("FC2", df, mix_tol=0.25) == "FAULT"
    assert _status("FC2", df, mix_tol=3.0) == "PASS"


def test_fc2_tol_not_algebraically_cancelled() -> None:
    # mat=46: FAULT at mix_tol=1.15 (threshold ~47.7) but PASS at 3.0 (threshold 44).
    df = _ts_df(12, mat=46.0, oa_t=50.0, rat=70.0, fan_cmd=50.0)
    m_tight = fc2(df, {"mix_tol": 1.15}, 300.0)
    m_loose = fc2(df, {"mix_tol": 3.0}, 300.0)
    assert bool(m_tight.any()) and not bool(m_loose.any())
    assert not m_tight.equals(m_loose)


def test_fc3_mix_tol_widens_envelope() -> None:
    df = _ts_df(24, mat=73.0, oa_t=50.0, rat=70.0, fan_cmd=50.0)
    assert _status("FC3", df, mix_tol=0.25) == "FAULT"
    assert _status("FC3", df, mix_tol=3.0) == "PASS"


def test_fc5_mix_tol_affects_mask() -> None:
    """Heating on; SAT/MAT near boundary — mix_tol must change raw mask."""
    df = _ts_df(12, sat=68.5, mat=70.0, htg_valve_pct=50.0, fan_cmd=50.0)
    m_tight = fc5(df, {"mix_tol": 0.25}, 300.0)
    m_loose = fc5(df, {"mix_tol": 3.0}, 300.0)
    assert not m_tight.equals(m_loose)


def test_fc2_fc3_source_rejects_same_side_tol_cancel() -> None:
    """Reject (x - tol) < min(... - tol) / (x - tol) > max(... - tol) same-side cancel."""
    cancel = re.compile(
        r"\(\s*\w+\s*-\s*tol\s*\)\s*[<>]=?\s*"
        r"(?:min|max|np\.minimum|np\.maximum)\s*\([^)]*-\s*tol",
        re.DOTALL,
    )
    for fn in (fc2, fc3, fc5):
        src = inspect.getsource(fn)
        assert cancel.search(src) is None, f"{fn.__name__} same-side tol cancel"


def test_oat_meteo_oat_err_affects_status() -> None:
    df = _ts_df(24, oa_t=80.0, wx_oa_t=70.0)
    assert _status("OAT-METEO", df, oat_err=5.0) == "FAULT"
    assert _status("OAT-METEO", df, oat_err=10.0) == "PASS"


def test_declared_band_params_have_sensitivity_coverage() -> None:
    """Hand table: band-like CookbookParams for FC2/3/5/OAT-METEO must be covered here."""
    covered = {
        ("FC2", "mix_tol"),
        ("FC3", "mix_tol"),
        ("FC5", "mix_tol"),
        ("OAT-METEO", "oat_err"),
    }
    band_re = re.compile(r"(tol|err|margin|band|approach)$", re.I)
    missing: list[str] = []
    for rid in ("FC2", "FC3", "FC5", "OAT-METEO"):
        rule = RULES_BY_ID[rid]
        for p in rule.params:
            if p.key == "confirm_min":
                continue
            if band_re.search(p.key) and (rid, p.key) not in covered:
                missing.append(f"{rid}.{p.key}")
    assert not missing, f"Add sensitivity cases for: {missing}"
