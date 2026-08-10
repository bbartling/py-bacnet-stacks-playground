"""Calendar-month helpers for IdealLoads gym farm / lookup."""
from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from .honesty import HONESTY_IDEALLOADS, LOOKUP_EMULATOR, PROMOTE
from .lookup_emulator import resolve_farm_root

DEPLOYABLE_STRATEGIES = (
    "baseline",
    "flat_24_7",
    "deep_setback",
    "stagger_preheat",
    "morning_all_on",
)

MONTHLY_PARQUET = "heating_dsm_eplus_paired_15min_monthly_v1.parquet"
PAIRED_PARQUET = "heating_dsm_eplus_paired_15min_v1.parquet"


def parse_month(yyyy_mm: str) -> tuple[int, int]:
    parts = str(yyyy_mm).strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"month must be YYYY-MM, got {yyyy_mm!r}")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12):
        raise ValueError(f"invalid month {yyyy_mm}")
    return year, month


def days_in_month(yyyy_mm: str) -> List[str]:
    year, month = parse_month(yyyy_mm)
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, d).isoformat() for d in range(1, n + 1)]


def build_month_scenarios(
    months: Sequence[str],
    strategies: Sequence[str],
) -> list[dict[str, Any]]:
    """One scenario per (day, strategy). baseline arm vs dsm arms."""
    scenarios: list[dict[str, Any]] = []
    for ym in months:
        for day in days_in_month(ym):
            for sid in strategies:
                arm = "baseline" if sid == "baseline" else "dsm"
                scenarios.append(
                    {
                        "day": day,
                        "month": ym,
                        "begin": date.fromisoformat(day),
                        "end": date.fromisoformat(day),
                        "arm": arm,
                        "strategy_id": sid,
                        "control_regime": sid,
                        "pair_id": f"{day}__{sid}",
                        "scenario_id": f"{day}_{sid}",
                    }
                )
    return scenarios


def farm_parquet_paths(site: Path) -> list[Path]:
    farm = resolve_farm_root(site)
    paths = []
    for name in (MONTHLY_PARQUET, PAIRED_PARQUET):
        p = farm / name
        if p.is_file():
            paths.append(p)
    return paths


def load_farm_frames(site: Path) -> pd.DataFrame:
    paths = farm_parquet_paths(site)
    if not paths:
        return pd.DataFrame()
    frames = [pd.read_parquet(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    if "day" in df.columns:
        df["day"] = df["day"].astype(str)
    if "strategy_id" in df.columns:
        df["strategy_id"] = df["strategy_id"].astype(str)
    # de-dupe prefer later rows
    if {"day", "strategy_id", "quarter_index"}.issubset(df.columns):
        df = df.drop_duplicates(
            subset=["day", "strategy_id", "quarter_index"], keep="last"
        )
    elif {"day", "strategy_id", "timestamp_utc"}.issubset(df.columns):
        df = df.drop_duplicates(
            subset=["day", "strategy_id", "timestamp_utc"], keep="last"
        )
    return df


def coverage_for_month(
    site: Path, yyyy_mm: str, strategies: Optional[Sequence[str]] = None
) -> dict[str, Any]:
    strats = list(strategies or DEPLOYABLE_STRATEGIES)
    wanted = set(days_in_month(yyyy_mm))
    df = load_farm_frames(site)
    by_strat: dict[str, list[str]] = {}
    if not df.empty and "day" in df.columns:
        for sid in strats:
            sub = df[df["strategy_id"] == sid]
            days = sorted(set(sub["day"].astype(str).unique()) & wanted)
            by_strat[sid] = days
    else:
        by_strat = {sid: [] for sid in strats}
    return {
        "month": yyyy_mm,
        "wanted_days": sorted(wanted),
        "n_wanted_days": len(wanted),
        "strategies": {
            sid: {
                "days_present": days,
                "n_days": len(days),
                "coverage_frac": (len(days) / len(wanted)) if wanted else 0.0,
            }
            for sid, days in by_strat.items()
        },
        "honesty": HONESTY_IDEALLOADS,
        "provenance": LOOKUP_EMULATOR,
        "promote": PROMOTE,
    }


def month_kpis(
    site: Path, yyyy_mm: str, strategies: Sequence[str]
) -> list[dict[str, Any]]:
    df = load_farm_frames(site)
    if df.empty:
        return []
    prefix = yyyy_mm
    kw_col = (
        "site_electric_proxy_kw"
        if "site_electric_proxy_kw" in df.columns
        else "facility_kw"
    )
    rows = []
    for sid in strategies:
        sub = df[
            (df["strategy_id"] == sid) & (df["day"].astype(str).str.startswith(prefix))
        ]
        if sub.empty or kw_col not in sub.columns:
            rows.append(
                {
                    "strategy_id": sid,
                    "month": yyyy_mm,
                    "n_days": 0,
                    "peak_kw": None,
                    "kwh": None,
                }
            )
            continue
        rows.append(
            {
                "strategy_id": sid,
                "month": yyyy_mm,
                "n_days": int(sub["day"].nunique()),
                "peak_kw": float(sub[kw_col].max()),
                "kwh": float(sub[kw_col].sum() * 0.25),
            }
        )
    return rows


def write_month_scorecard(
    out_dir: Path,
    *,
    yyyy_mm: str,
    strategies: Sequence[str],
    site: Path,
    extra: Optional[dict[str, Any]] = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cov = coverage_for_month(site, yyyy_mm, strategies)
    card = {
        "month": yyyy_mm,
        "strategies": list(strategies),
        "coverage": cov,
        "kpis": month_kpis(site, yyyy_mm, strategies),
        "honesty": HONESTY_IDEALLOADS,
        "promote": PROMOTE,
        "note": "IdealLoads STRUCTURAL_LOAD_DIAGNOSTIC — not BAS meter truth",
    }
    if extra:
        card["extra"] = extra
    path = out_dir / f"{yyyy_mm}_scorecard.json"
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    return path


def filter_days_for_month(days: Sequence[str], yyyy_mm: str) -> List[str]:
    return [d for d in days if str(d).startswith(yyyy_mm)]
