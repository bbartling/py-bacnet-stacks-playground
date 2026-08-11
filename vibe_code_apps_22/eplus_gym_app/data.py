"""Data loaders for Lakeside E+ gym Streamlit app (no EnergyPlus)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.honesty import HONESTY_IDEALLOADS, LOOKUP_EMULATOR, PROMOTE
from eplus_gym.month_calendar import (
    DEPLOYABLE_STRATEGIES,
    coverage_for_month,
    load_farm_frames,
    month_kpis,
)
from lakeside.paths import site_root


def resolve_site() -> Path:
    return Path(os.environ.get("LAKESIDE_SITE_ROOT") or site_root())


def available_months(site: Optional[Path] = None) -> list[str]:
    site = Path(site or resolve_site())
    df = load_farm_frames(site)
    defaults = ["2026-01", "2026-02"]
    if df.empty or "day" not in df.columns:
        return defaults
    found = sorted({str(d)[:7] for d in df["day"].astype(str) if len(str(d)) >= 7})
    # keep defaults first if present
    out = [m for m in defaults if m in found]
    out.extend(m for m in found if m not in out)
    return out or defaults


def load_month_slice(
    month: str,
    strategies: Sequence[str],
    site: Optional[Path] = None,
) -> pd.DataFrame:
    site = Path(site or resolve_site())
    df = load_farm_frames(site)
    if df.empty:
        return df
    strats = set(strategies)
    mask = df["day"].astype(str).str.startswith(month) & df["strategy_id"].isin(strats)
    sub = df.loc[mask].copy()
    kw = (
        "site_electric_proxy_kw"
        if "site_electric_proxy_kw" in sub.columns
        else "facility_kw"
    )
    if kw != "facility_kw" and "facility_kw" not in sub.columns:
        sub["facility_kw"] = sub[kw]
    return sub


def month_summary(
    month: str,
    strategies: Sequence[str],
    site: Optional[Path] = None,
) -> dict[str, Any]:
    site = Path(site or resolve_site())
    cov = coverage_for_month(site, month, strategies)
    kpis = month_kpis(site, month, strategies)
    score_path = (
        _APP / "reports" / "eplus_gym" / "monthly" / f"{month}_scorecard.json"
    )
    scorecard = None
    if score_path.is_file():
        scorecard = json.loads(score_path.read_text(encoding="utf-8"))
    return {
        "month": month,
        "coverage": cov,
        "kpis": kpis,
        "scorecard": scorecard,
        "honesty": HONESTY_IDEALLOADS,
        "provenance": LOOKUP_EMULATOR,
        "promote": PROMOTE,
        "strategies": list(strategies or DEPLOYABLE_STRATEGIES),
    }


def mean_daily_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """Return long frame: strategy_id, step, facility_kw (mean over days)."""
    if df.empty or "facility_kw" not in df.columns:
        return pd.DataFrame(columns=["strategy_id", "step", "facility_kw"])
    if "step" not in df.columns and "quarter_index" in df.columns:
        df = df.copy()
        df["step"] = df["quarter_index"]
    if "step" not in df.columns:
        return pd.DataFrame(columns=["strategy_id", "step", "facility_kw"])
    g = (
        df.groupby(["strategy_id", "step"], as_index=False)["facility_kw"]
        .mean()
        .sort_values(["strategy_id", "step"])
    )
    return g
