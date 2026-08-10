"""Same-day peak-demand shape gallery (meter · E+ · ML) for load-profile notebooks.

Anchor day = local calendar day of max 5-min meter kW — same rule as
``demand_vs_web_weather_scatter_peak_day.png``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PeakDayGallery:
    peak_day: str
    peak_kw: float
    peak_ts_local: str
    actual_kw: np.ndarray | None = None
    eplus_kw: np.ndarray | None = None
    ml_baseline_kw: np.ndarray | None = None
    ml_hybrid_kw: np.ndarray | None = None
    labels: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def load_meter_demand(meter_csv: Path) -> pd.DataFrame:
    demand = pd.read_csv(meter_csv)
    demand["timestamp_utc"] = pd.to_datetime(demand["timestamp_utc"], utc=True)
    demand = demand.sort_values("timestamp_utc").dropna(subset=["kw_demand"])
    demand["ts_local"] = demand["timestamp_utc"].dt.tz_convert("America/Chicago")
    demand["hour"] = demand["ts_local"].dt.hour
    demand["day"] = demand["ts_local"].dt.strftime("%Y-%m-%d")
    demand["is_weekend"] = demand["ts_local"].dt.dayofweek >= 5
    return demand


def find_peak_demand_day(demand: pd.DataFrame) -> tuple[str, float, pd.Timestamp]:
    """Local calendar day containing the max 5-min kW (matches demand_weather_charts)."""
    peak_idx = demand["kw_demand"].idxmax()
    peak_ts = demand.loc[peak_idx, "ts_local"]
    peak_day = peak_ts.strftime("%Y-%m-%d")
    peak_kw = float(demand.loc[peak_idx, "kw_demand"])
    return peak_day, peak_kw, peak_ts


def meter_hourly_kw(demand: pd.DataFrame, day: str) -> np.ndarray | None:
    sub = demand[demand["day"] == day]
    if sub.empty:
        return None
    return sub.groupby("hour")["kw_demand"].mean().reindex(range(24)).to_numpy(dtype=float)


def _sort_day_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ("step_15", "quarter_index", "hour_ending", "minute") if c in df.columns]
    return df.sort_values(cols) if cols else df


def _hourly_from_day_frame(sub: pd.DataFrame, kw_col: str = "facility_kw") -> np.ndarray | None:
    if sub.empty or kw_col not in sub.columns:
        return None
    sub = _sort_day_frame(sub)
    if "step_15" in sub.columns and len(sub) >= 96:
        kw = sub[kw_col].to_numpy(dtype=float)[:96]
        return np.array([kw[i * 4 : (i + 1) * 4].mean() for i in range(24)], dtype=float)
    if "hour_ending" in sub.columns:
        return (
            sub.groupby("hour_ending")[kw_col]
            .mean()
            .reindex(range(24))
            .to_numpy(dtype=float)
        )
    if len(sub) >= 96:
        kw = sub[kw_col].to_numpy(dtype=float)[:96]
        return np.array([kw[i * 4 : (i + 1) * 4].mean() for i in range(24)], dtype=float)
    return None


def eplus_baseline_hourly(paired_parquet: Path, day: str) -> np.ndarray | None:
    if not paired_parquet.is_file():
        return None
    ep_b = _eplus_baseline_frame(paired_parquet)
    if ep_b is None or "day" not in ep_b.columns:
        return None
    sub = ep_b[ep_b["day"].astype(str) == day]
    return _hourly_from_day_frame(sub)


def _eplus_baseline_frame(paired_parquet: Path) -> pd.DataFrame | None:
    if not paired_parquet.is_file():
        return None
    ep = pd.read_parquet(paired_parquet)
    if "control_regime" in ep.columns:
        return ep[ep["control_regime"].astype(str).str.contains("baseline", case=False, na=False)]
    if "strategy_id" in ep.columns:
        return ep[ep["strategy_id"].astype(str) == "baseline"]
    return ep


def oat_hourly_from_day_frame(sub: pd.DataFrame) -> np.ndarray | None:
    if sub.empty or "oat_f" not in sub.columns:
        return None
    sub = _sort_day_frame(sub)
    if "hour_ending" in sub.columns:
        return (
            sub.groupby("hour_ending")["oat_f"]
            .mean()
            .reindex(range(24))
            .interpolate()
            .bfill()
            .ffill()
            .to_numpy(dtype=float)
        )
    if "step_15" in sub.columns and len(sub) >= 96:
        oat = sub["oat_f"].to_numpy(dtype=float)[:96]
        return np.array([oat[i * 4 : (i + 1) * 4].mean() for i in range(24)], dtype=float)
    if len(sub) >= 24:
        oat = sub["oat_f"].to_numpy(dtype=float)
        return np.array([oat[i * (len(oat) // 24) : (i + 1) * (len(oat) // 24)].mean() for i in range(24)], dtype=float)
    return None


def query_oat_hourly(
    *,
    peak_day: str,
    bas: pd.DataFrame | None,
    demand: pd.DataFrame | None = None,
    weather_csv: Path | None = None,
) -> np.ndarray | None:
    """OAT trajectory for the peak day — prefer BAS, else weather sidecar."""
    if bas is not None:
        sub = _bas_day_frame(bas, peak_day)
        oat = oat_hourly_from_day_frame(sub)
        if oat is not None and np.isfinite(oat).any():
            return oat
    if weather_csv is not None and weather_csv.is_file() and demand is not None:
        wx = pd.read_csv(weather_csv)
        wx["timestamp_utc"] = pd.to_datetime(wx["timestamp_utc"], utc=True)
        col = "web-outside-air-temp" if "web-outside-air-temp" in wx.columns else None
        if col is None:
            return None
        day_mask = demand["day"] == peak_day
        if not day_mask.any():
            return None
        # align weather onto peak-day meter timestamps (hourly mean)
        dsub = demand.loc[day_mask, ["timestamp_utc", "hour"]].copy()
        dsub["hour_utc"] = dsub["timestamp_utc"].dt.floor("h")
        w = wx.copy()
        w["hour_utc"] = w["timestamp_utc"].dt.floor("h")
        m = dsub.merge(w[["hour_utc", col]], on="hour_utc", how="left")
        return m.groupby("hour")[col].mean().reindex(range(24)).interpolate().bfill().ffill().to_numpy(dtype=float)
    return None


def eplus_best_weather_match(
    paired_parquet: Path,
    query_oat_24: np.ndarray,
    *,
    prefer_weekend: bool | None = None,
) -> tuple[str, np.ndarray, float] | None:
    """Pick E+ baseline day with closest hourly OAT (RMSE). Optional weekend preference."""
    ep_b = _eplus_baseline_frame(paired_parquet)
    if ep_b is None or "day" not in ep_b.columns or "oat_f" not in ep_b.columns:
        return None
    q = np.asarray(query_oat_24, dtype=float)
    if q.shape != (24,) or not np.isfinite(q).all():
        return None

    best: tuple[str, np.ndarray, float] | None = None
    for day, sub in ep_b.groupby(ep_b["day"].astype(str)):
        oat = oat_hourly_from_day_frame(sub)
        kw = _hourly_from_day_frame(sub)
        if oat is None or kw is None or not np.isfinite(oat).all():
            continue
        rmse = float(np.sqrt(np.mean((oat - q) ** 2)))
        # Soft weekend/weekday preference (small tie-break, not a hard filter)
        if prefer_weekend is not None and "is_weekend" in sub.columns:
            day_we = bool(sub["is_weekend"].iloc[0])
            if day_we != prefer_weekend:
                rmse += 1.5  # °F-equivalent penalty
        if best is None or rmse < best[2]:
            best = (str(day), kw, rmse)
    return best


def _bas_day_frame(bas: pd.DataFrame, day: str) -> pd.DataFrame:
    sub = bas[bas["day"].astype(str) == day].copy()
    return _sort_day_frame(sub)


def ml_hybrid_hourly_for_day(
    *,
    bas: pd.DataFrame | None,
    day: str,
    artifacts_dir: Path,
    strategy_id: str = "stagger_preheat",
) -> tuple[np.ndarray | None, np.ndarray | None, str]:
    """ONNX hybrid walk for ``day`` using measured midnight + day's OAT from BAS store."""
    try:
        from hybrid_rollout import (  # local import — notebook path
            STEPS,
            load_hybrid_onnx,
            rollout_96,
            schedule_from_strategy_fixture,
        )
        from feature_compile_heating_dsm import ZONE_TEMP_COLS, STRATEGY_IDS
    except Exception as e:
        return None, None, f"ML imports failed: {e}"

    if bas is None:
        return None, None, "BAS frame unavailable for ML day walk"
    sub = _bas_day_frame(bas, day)
    if len(sub) < 80:
        return None, None, f"BAS has <80 rows for {day}"

    base_onnx = artifacts_dir / "real_baseline_15min_v1.onnx"
    delta_onnx = artifacts_dir / "eplus_delta_15min_v1.onnx"
    if not base_onnx.is_file() or not delta_onnx.is_file():
        return None, None, f"ONNX missing under {artifacts_dir}"

    try:
        models = load_hybrid_onnx(base_onnx, delta_onnx)
    except Exception as e:
        return None, None, f"ONNX load failed: {e}"

    row0 = sub.iloc[0]
    oat = sub["oat_f"].to_numpy(dtype=float) if "oat_f" in sub.columns else np.full(len(sub), 20.0)
    if len(oat) >= 96:
        oat_96 = oat[:96]
    else:
        # upsample / pad hourly means to 96
        if "hour_ending" in sub.columns:
            h = sub.groupby("hour_ending")["oat_f"].mean().reindex(range(24)).interpolate().bfill().ffill()
            oat_96 = np.repeat(h.to_numpy(dtype=float), 4)
        else:
            oat_96 = np.resize(oat, 96)

    zones = []
    for c in ZONE_TEMP_COLS:
        if c in sub.columns:
            zones.append(float(sub.iloc[0][c]))
        else:
            zones.append(62.0)

    sid = strategy_id if strategy_id in STRATEGY_IDS else STRATEGY_IDS[0]
    baseline_id = "baseline" if "baseline" in STRATEGY_IDS else STRATEGY_IDS[0]
    try:
        dsm_sched = schedule_from_strategy_fixture(sid)
        base_sched = schedule_from_strategy_fixture(baseline_id)
    except Exception as e:
        return None, None, f"control schedule failed: {e}"

    month = float(row0["month"]) if "month" in sub.columns else float(pd.Timestamp(day).month)
    doy = float(row0["doy"]) if "doy" in sub.columns else float(pd.Timestamp(day).dayofyear)
    is_weekend = float(row0["is_weekend"]) if "is_weekend" in sub.columns else float(
        pd.Timestamp(day).dayofweek >= 5
    )
    occ = [1.0 if 7 <= (s // 4) < 18 else 0.0 for s in range(STEPS)]

    contract = {
        "contract_version": "hybrid_dsm_96_v1",
        "init": {
            "facility_kw": float(row0["facility_kw"]),
            "oat_f": float(oat_96[0]),
            **{ZONE_TEMP_COLS[i]: zones[i] for i in range(6)},
        },
        "weather_forecast_96": {
            "oat_f": [float(x) for x in oat_96],
            "rh_pct": [float(x) for x in (sub["rh_pct"].to_numpy()[:96] if "rh_pct" in sub.columns else np.full(96, 55.0))],
            "ghi": [float(x) for x in (sub["ghi"].to_numpy()[:96] if "ghi" in sub.columns else np.zeros(96))],
        },
        "baseline_control_96": base_sched,
        "dsm_control_96": dsm_sched,
        "calendar": {
            "month": month,
            "doy": doy,
            "is_weekend": is_weekend,
            "occupied_schedule": occ,
        },
        "comfort_htg_sp_f": 68.0,
        "comfort_band_f": 2.0,
        "strategy_id": sid,
    }
    # pad rh/ghi to 96
    for k in ("rh_pct", "ghi"):
        series = contract["weather_forecast_96"][k]
        if len(series) < 96:
            contract["weather_forecast_96"][k] = list(series) + [series[-1]] * (96 - len(series))
        else:
            contract["weather_forecast_96"][k] = list(series[:96])

    try:
        walk = rollout_96(models, contract)
    except Exception as e:
        return None, None, f"rollout failed: {e}"

    steps = walk.get("steps") or []
    if len(steps) < 96:
        return None, None, "rollout returned <96 steps"
    b = np.array([float(s["baseline_facility_kw"]) for s in steps[:96]], dtype=float)
    h = np.array([float(s["hybrid_facility_kw"]) for s in steps[:96]], dtype=float)
    ml_base = np.array([b[i * 4 : (i + 1) * 4].mean() for i in range(24)], dtype=float)
    ml_hyb = np.array([h[i * 4 : (i + 1) * 4].mean() for i in range(24)], dtype=float)
    return ml_base, ml_hyb, f"ONNX hybrid {sid} on {day}"


def build_peak_day_gallery(
    *,
    meter_csv: Path,
    paired_parquet: Path,
    artifacts_dir: Path,
    bas: pd.DataFrame | None = None,
    strategy_id: str = "stagger_preheat",
    weather_csv: Path | None = None,
    allow_eplus_weather_match: bool = True,
) -> PeakDayGallery:
    """Build Actual / E+ / ML hourly kW for the meter peak-demand day.

    E+ uses the exact calendar day when farmed; otherwise (optional) the baseline
    farm day with the closest hourly OAT to the peak day.
    """
    demand = load_meter_demand(meter_csv)
    peak_day, peak_kw, peak_ts = find_peak_demand_day(demand)
    g = PeakDayGallery(
        peak_day=peak_day,
        peak_kw=peak_kw,
        peak_ts_local=str(peak_ts),
        labels={"actual": "n/a", "eplus": "n/a", "ml": "n/a"},
    )
    g.notes.append(
        f"Anchor = peak meter day {peak_day} (max 5-min kW={peak_kw:.1f} at {peak_ts}) "
        "— same rule as demand_vs_web_weather_scatter_peak_day.png"
    )

    actual = meter_hourly_kw(demand, peak_day)
    if actual is not None:
        g.actual_kw = actual
        g.labels["actual"] = f"meter {peak_day}"
    else:
        g.notes.append(f"meter missing hourly for {peak_day}")

    eplus = eplus_baseline_hourly(paired_parquet, peak_day)
    if eplus is not None and np.isfinite(eplus).any():
        g.eplus_kw = eplus
        g.labels["eplus"] = f"E+ IdealLoads {peak_day} (exact day)"
    elif allow_eplus_weather_match:
        q_oat = query_oat_hourly(
            peak_day=peak_day,
            bas=bas,
            demand=demand,
            weather_csv=weather_csv,
        )
        prefer_we = bool(peak_ts.dayofweek >= 5)
        match = eplus_best_weather_match(
            paired_parquet, q_oat, prefer_weekend=prefer_we
        ) if q_oat is not None else None
        if match is not None:
            mday, mkw, rmse = match
            g.eplus_kw = mkw
            g.labels["eplus"] = f"E+ weather-match {mday} (OAT RMSE {rmse:.1f}°F)"
            g.notes.append(
                f"No E+ farm day for {peak_day}; showing best OAT-matched baseline "
                f"{mday} (hourly OAT RMSE={rmse:.2f}°F). Shape proxy — not same calendar day."
            )
        else:
            g.notes.append(
                f"E+ farm has no baseline for {peak_day} and weather-match failed "
                "(need oat_f on farm days + query OAT from BAS/weather)."
            )
            g.labels["eplus"] = f"missing · no E+ match for {peak_day}"
    else:
        g.notes.append(f"E+ paired farm has no baseline day {peak_day}")
        g.labels["eplus"] = f"missing · no E+ for {peak_day}"

    ml_b, ml_h, ml_note = ml_hybrid_hourly_for_day(
        bas=bas,
        day=peak_day,
        artifacts_dir=artifacts_dir,
        strategy_id=strategy_id,
    )
    if ml_b is not None:
        g.ml_baseline_kw = ml_b
        g.ml_hybrid_kw = ml_h
        g.labels["ml"] = ml_note
    else:
        g.notes.append(ml_note)
        g.labels["ml"] = f"missing · {ml_note[:60]}"

    return g
