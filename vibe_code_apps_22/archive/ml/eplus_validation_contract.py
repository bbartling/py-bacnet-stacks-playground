"""Canonical EnergyPlus ↔ measured validation contract (no blended sources).

Products (never mixed):
  A. utility_bill_monthly
  B. interval_meter_monthly
  C. interval_hourly
  D. interval_15min_dsm_diagnostic

Alignment rules:
  - Join only on explicit timestamp keys (interval end, UTC for measured;
    E+ LST → UTC via fixed CST−6).
  - Reject length/shape mismatches (no silent truncation).
  - Reject duplicate timestamps unless a documented rule applies.
  - Design-day / sizing duplicates: keep **last** occurrence per E+ stamp
    (annual run follows the design-day block in meter CSV).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from eplus_native.align import (
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    parse_eplus_csv_timestamp,
)
from eplus_native.extract import load_timestep_proxy_kw
from eplus_native.hashes import sha256_file
from eplus_multires_metrics import nmbe_cvrmse_pct, resolution_block

SourceType = Literal[
    "utility_bill_monthly",
    "interval_meter_monthly",
    "interval_hourly",
    "interval_15min",
    "eplus_timestep",
]


@dataclass
class SeriesProvenance:
    source_type: SourceType
    source_path: str
    source_sha256: str | None
    interval_minutes: int
    timezone: str
    timestamp_convention: str  # "interval_end"
    environment: str | None = None
    notes: str | None = None


class AlignmentError(ValueError):
    """Fail-closed alignment / integrity error."""


def reject_shape_mismatch(a: np.ndarray, b: np.ndarray, *, label: str = "series") -> None:
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        raise AlignmentError(
            f"{label} shape mismatch: observed{a.shape} vs simulated{b.shape} — refuse truncate"
        )


def dedupe_eplus_stamps_keep_last(df: pd.DataFrame, *, stamp_col: str = "eplus_stamp") -> pd.DataFrame:
    """Drop design-day duplicates: keep last row per stamp (annual follows sizing)."""
    if stamp_col not in df.columns:
        raise AlignmentError(f"missing {stamp_col}")
    before = len(df)
    out = df.drop_duplicates(subset=[stamp_col], keep="last").copy()
    out.attrs["dedupe_dropped"] = int(before - len(out))
    out.attrs["dedupe_rule"] = "keep_last_per_eplus_stamp_annual_after_design_day"
    return out


def parse_eplus_proxy_to_utc(
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    amy_start_month: int = 8,
) -> pd.DataFrame:
    """Load timestep proxy kW, dedupe design-day stamps, attach interval_end UTC."""
    raw = load_timestep_proxy_kw(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop, interval_hours=0.25)
    raw = dedupe_eplus_stamps_keep_last(raw)
    rows = []
    for _, r in raw.iterrows():
        stamp = str(r["eplus_stamp"]).strip()
        month = int(stamp.split("/")[0]) if "/" in stamp else 1
        year = 2025 if month >= amy_start_month else 2026
        dt = parse_eplus_csv_timestamp(stamp, year_hint=year)
        if dt is None:
            continue
        rows.append(
            {
                "eplus_stamp": stamp,
                "interval_end_utc": dt.astimezone(timezone.utc),
                "interval_end_lst": dt,
                "simulated_kw": float(r["site_electric_proxy_kw"]),
                "environment": "annual_amy_after_design_day_dedupe",
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise AlignmentError(f"no usable E+ rows from {sim_dir}")
    # Reject remaining duplicate UTC keys
    if out["interval_end_utc"].duplicated().any():
        n_dup = int(out["interval_end_utc"].duplicated().sum())
        raise AlignmentError(f"duplicate interval_end_utc after dedupe: {n_dup}")
    out["interval_end_utc"] = pd.to_datetime(out["interval_end_utc"], utc=True)
    out.attrs["provenance"] = asdict(
        SeriesProvenance(
            source_type="eplus_timestep",
            source_path=str(Path(sim_dir).resolve()),
            source_sha256=None,
            interval_minutes=15,
            timezone="E+ LST CST-6 → UTC",
            timestamp_convention="interval_end",
            environment="annual_amy_after_design_day_dedupe",
            notes=f"dedupe_dropped={raw.attrs.get('dedupe_dropped')}",
        )
    )
    return out


def load_measured_interval(root: Path) -> tuple[pd.DataFrame, SeriesProvenance]:
    path = Path(root) / "utilities" / "demand_interval_kw.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "timestamp_utc" not in df.columns or "kw_demand" not in df.columns:
        raise AlignmentError("demand_interval_kw.csv needs timestamp_utc, kw_demand")
    df = df.copy()
    df["interval_end_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    if df["interval_end_utc"].duplicated().any():
        raise AlignmentError("duplicate timestamps in measured demand_interval_kw.csv")
    prov = SeriesProvenance(
        source_type="interval_hourly",  # raw is typically 5-min; marked at load site
        source_path=str(path.resolve()),
        source_sha256=sha256_file(path),
        interval_minutes=5,
        timezone="UTC",
        timestamp_convention="interval_end",
        notes="raw meter intervals before aggregation",
    )
    return df, prov


def align_interval(
    measured_agg: pd.DataFrame,
    modeled: pd.DataFrame,
    *,
    meas_kw_col: str,
    mod_kw_col: str = "simulated_kw",
    ts_col: str = "interval_end_utc",
    completeness_min: float = 0.0,
) -> pd.DataFrame:
    """Inner-join on timestamp; fail on empty; attach completeness."""
    m = measured_agg[[ts_col, meas_kw_col]].rename(columns={meas_kw_col: "observed_kw"})
    s = modeled[[ts_col, mod_kw_col]].rename(columns={mod_kw_col: "simulated_kw"})
    m[ts_col] = pd.to_datetime(m[ts_col], utc=True)
    s[ts_col] = pd.to_datetime(s[ts_col], utc=True)
    if m[ts_col].duplicated().any() or s[ts_col].duplicated().any():
        raise AlignmentError("duplicate timestamps before align — refuse")
    aligned = m.merge(s, on=ts_col, how="inner")
    if aligned.empty:
        raise AlignmentError("zero overlapping timestamps after align")
    reject_shape_mismatch(
        aligned["observed_kw"].to_numpy(),
        aligned["simulated_kw"].to_numpy(),
        label="aligned_kw",
    )
    aligned = aligned.dropna(subset=["observed_kw", "simulated_kw"])
    aligned["completeness_fraction"] = 1.0
    if completeness_min > 0 and float(aligned["completeness_fraction"].min()) < completeness_min:
        raise AlignmentError("completeness below threshold")
    aligned["timestamp"] = aligned[ts_col]
    aligned["interval_end"] = aligned[ts_col]
    aligned["timezone"] = "UTC"
    return aligned.sort_values(ts_col).reset_index(drop=True)


def build_hourly_and_15min(
    root: Path,
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
) -> dict[str, Any]:
    """Build aligned hourly + 15-min products with provenance."""
    meas, mprov = load_measured_interval(root)
    # Prefer original CSV timestamp_utc when present; avoid duplicate rename keys.
    if "timestamp_utc" in meas.columns:
        meas_for_agg = meas[["timestamp_utc", "kw_demand"]].copy()
    else:
        meas_for_agg = meas[["interval_end_utc", "kw_demand"]].rename(
            columns={"interval_end_utc": "timestamp_utc"}
        )
    hourly_m = aggregate_5min_to_hourly_mean(
        meas_for_agg,
        ts_col="timestamp_utc",
        kw_col="kw_demand",
    ).rename(columns={"timestamp_utc": "interval_end_utc", "kw_mean": "observed_kw"})
    q15_m = aggregate_5min_to_15min_mean(
        meas_for_agg,
        ts_col="timestamp_utc",
        kw_col="kw_demand",
    ).rename(columns={"timestamp_utc": "interval_end_utc", "kw_mean": "observed_kw"})

    mod = parse_eplus_proxy_to_utc(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    mod_h = (
        mod.set_index("interval_end_utc")["simulated_kw"]
        .resample("1h", label="right", closed="right")
        .mean()
        .rename("simulated_kw")
        .to_frame()
        .reset_index()
    )
    mod_15 = (
        mod.set_index("interval_end_utc")["simulated_kw"]
        .resample("15min", label="right", closed="right")
        .mean()
        .rename("simulated_kw")
        .to_frame()
        .reset_index()
    )
    aligned_h = align_interval(hourly_m, mod_h, meas_kw_col="observed_kw")
    aligned_15 = align_interval(q15_m, mod_15, meas_kw_col="observed_kw")
    return {
        "hourly": aligned_h,
        "q15": aligned_15,
        "measured_provenance": asdict(mprov),
        "modeled_provenance": mod.attrs.get("provenance"),
        "dedupe_dropped": (mod.attrs.get("provenance") or {}).get("notes"),
    }


def score_aligned(aligned: pd.DataFrame, *, resolution: str, p: int = 1) -> dict[str, Any]:
    reject_shape_mismatch(aligned["observed_kw"].to_numpy(), aligned["simulated_kw"].to_numpy())
    block = resolution_block(
        aligned["observed_kw"], aligned["simulated_kw"], resolution=resolution, p=p
    )
    yt = aligned["observed_kw"].to_numpy(dtype=float)
    yp = aligned["simulated_kw"].to_numpy(dtype=float)
    err = yp - yt
    block["rmse_kw"] = float(np.sqrt(np.mean(err**2)))
    block["mae_kw"] = float(np.mean(np.abs(err)))
    block["mbe_kw"] = float(np.mean(err))
    # Defend p: calibrated-sim convention p=1 (one overall bias / calibration DOF).
    block["p_rationale"] = (
        "p=1 follows common calibrated-simulation reporting (one overall calibration "
        "degree of freedom). Not a purchased ASHRAE G14-2023 citation. n and p published "
        "with every score."
    )
    return block


def observed_monthly_utility_path(root: Path) -> Path:
    return Path(root) / "reports" / "eplus" / "observed_monthly_utility.csv"


def parse_complete_month_flag(val: Any) -> bool:
    """Parse textual/numeric ``complete_month`` values fail-closed."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, np.integer)):
        if int(val) in (0, 1):
            return bool(int(val))
        raise AlignmentError(f"unparseable complete_month int: {val!r}")
    if isinstance(val, float):
        if val in (0.0, 1.0) and val == val:
            return bool(int(val))
        raise AlignmentError(f"unparseable complete_month float: {val!r}")
    s = str(val).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n", ""}:
        return False
    raise AlignmentError(f"unparseable complete_month value: {val!r}")


def load_observed_monthly_utility(root: Path) -> pd.DataFrame:
    """Load the 10 complete utility-bill months (fixed measured source)."""
    path = observed_monthly_utility_path(root)
    if not path.is_file():
        raise AlignmentError(f"missing observed utility monthly CSV: {path}")
    df = pd.read_csv(path)
    need = {"month", "kwh_obs"}
    if not need.issubset(df.columns):
        raise AlignmentError(f"{path} needs columns {need}")
    if "complete_month" in df.columns:
        mask = df["complete_month"].map(parse_complete_month_flag)
        df = df.loc[mask].copy()
    if "source" in df.columns and (df["source"] != "utility_bill").any():
        raise AlignmentError("observed_monthly_utility.csv contains non-utility_bill rows")
    if df.empty:
        raise AlignmentError("no complete utility months")
    return df.reset_index(drop=True)


# Expected 15-min intervals in a non-DST month (31d * 96); DST months vary ±1h.
_MIN_COMPLETE_MONTH_INTERVALS = 28 * 96  # fail incomplete calendar months


def trial_simulated_monthly_kwh(
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    min_intervals: int = _MIN_COMPLETE_MONTH_INTERVALS,
) -> pd.DataFrame:
    """Aggregate trial proxy kW → monthly kWh with interval-completeness guard."""
    mod = parse_eplus_proxy_to_utc(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    # 15-min mean kW × 0.25 h = kWh
    df = mod.copy()
    df["kwh"] = df["simulated_kw"].astype(float) * 0.25
    local = pd.to_datetime(df["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
    df["month"] = local.dt.strftime("%Y-%m")
    grouped = df.groupby("month", as_index=False).agg(
        kwh_sim=("kwh", "sum"),
        n_intervals=("kwh", "count"),
    )
    # Drop incomplete months (edge AMY months); pairing later fails closed if needed.
    complete = grouped[grouped["n_intervals"] >= int(min_intervals)].copy()
    dropped = grouped[grouped["n_intervals"] < int(min_intervals)]
    if len(dropped):
        complete.attrs["dropped_incomplete_months"] = dropped[
            ["month", "n_intervals"]
        ].to_dict(orient="records")
    return complete[["month", "kwh_sim"]]


def utility_monthly_from_trial_sim(
    root: Path,
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
) -> dict[str, Any]:
    """Product A for a trial: pair observed utility months with THIS trial's sim kWh.

    Never imports pass/fail from best_scorecard_utility.json / gl14_status.
    Fail-closed if months cannot be paired.
    """
    from eplus_multires_metrics import gate_monthly

    obs_path = observed_monthly_utility_path(root)
    obs = load_observed_monthly_utility(root)
    sim = trial_simulated_monthly_kwh(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    paired = obs.merge(sim, on="month", how="inner")
    if len(paired) != len(obs):
        missing = sorted(set(obs["month"]) - set(paired["month"]))
        raise AlignmentError(
            f"trial monthly utility pairing incomplete: need {len(obs)} months, "
            f"got {len(paired)}; missing={missing}"
        )
    reject_shape_mismatch(paired["kwh_obs"].to_numpy(), paired["kwh_sim"].to_numpy(), label="utility_monthly")
    stats = nmbe_cvrmse_pct(paired["kwh_obs"], paired["kwh_sim"], p=1)
    status = gate_monthly(stats)
    rows = [
        {
            "month": str(r["month"]),
            "kwh_obs": float(r["kwh_obs"]),
            "kwh_sim": float(r["kwh_sim"]),
        }
        for _, r in paired.iterrows()
    ]
    return {
        "resolution": "monthly",
        "source_type": "utility_bill_monthly",
        "status": status,
        "n": int(stats["n"]),
        "p": 1,
        "nmbe_pct": stats["nmbe_pct"],
        "cvrmse_pct": stats["cvrmse_pct"],
        "mean_obs": stats["mean_obs"],
        "rmse_kw": None,
        "mae_kw": None,
        "labeled_as_gl14": False,
        "partial_period_monthly_threshold_screen": True,
        "label": "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN (utility bills, trial-specific)",
        "complete_months": int(len(paired)),
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "p_rationale": "p=1 calibrated-sim convention; n=complete utility months paired to trial sim",
        "formula": stats.get("formula"),
        "denominator": "n-p",
        "observed_source_path": str(obs_path.resolve()),
        "observed_source_sha256": sha256_file(obs_path),
        "sim_dir": str(Path(sim_dir).resolve()),
        "heat_cop": float(heat_cop),
        "cool_cop": float(cool_cop),
        "monthly_pairs": rows,
        "scorecard_gl14_status_imported": False,
    }


def utility_monthly_from_scorecard(root: Path) -> dict[str, Any] | None:
    """Champion REFERENCE ONLY — never use for trial scoring or promotion.

    Prefer ``utility_monthly_from_trial_sim`` for any campaign trial.
    Recomputes gates from stored nmbe/cvrmse numbers; ignores gl14_status for pass/fail.
    """
    sc = Path(root) / "eplus" / "scorecards" / "best_scorecard_utility.json"
    if not sc.is_file():
        return None
    doc = json_load(sc)
    g = doc.get("gl14") or {}
    monthly = doc.get("monthly") or []
    n = int(g.get("n") or len(monthly))
    block = {
        "resolution": "monthly",
        "source_type": "utility_bill_monthly",
        "source_path": str(sc.resolve()),
        "source_sha256": sha256_file(sc),
        "n": n,
        "p": 1,
        "nmbe_pct": g.get("nmbe_pct"),
        "cvrmse_pct": g.get("cvrmse_pct"),
        "mean_obs": g.get("mean_obs"),
        "rmse_kw": None,
        "mae_kw": None,
        "labeled_as_gl14": False,
        "partial_period_monthly_threshold_screen": True,
        "label": "CHAMPION REFERENCE ONLY (not trial-specific) — PARTIAL-PERIOD SCREEN",
        "complete_months": n,
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "p_rationale": (
            "p=1 calibrated-sim convention; champion scorecard reference — do not use for trials"
        ),
        "formula": "NMBE%=100*sum(m-ŷ)/((n-p)*mean(m)); CVRMSE%=100*sqrt(sum((m-ŷ)^2)/(n-p))/mean(m)",
        "champion_reference_only": True,
        "scorecard_gl14_status_imported": False,
        "scorecard_gl14_status_raw": doc.get("gl14_status"),
    }
    from eplus_multires_metrics import gate_monthly

    if block["nmbe_pct"] is not None and block["cvrmse_pct"] is not None:
        block["status"] = gate_monthly(block)
    else:
        block["status"] = "insufficient_data"
    return block


def interval_monthly_from_aligned_hourly(aligned_h: pd.DataFrame) -> dict[str, Any]:
    """Product B: interval meter aggregated to monthly energy (kWh), not utility bills."""
    from eplus_multires_metrics import gate_monthly

    df = aligned_h.copy()
    df["month"] = (
        pd.to_datetime(df["interval_end_utc"], utc=True)
        .dt.tz_convert("America/Chicago")
        .dt.strftime("%Y-%m")
    )
    rows = []
    for month, g in df.groupby("month"):
        rows.append(
            {
                "month": month,
                "kwh_obs": float(g["observed_kw"].sum()),
                "kwh_sim": float(g["simulated_kw"].sum()),
                "n_hours": int(len(g)),
            }
        )
    mdf = pd.DataFrame(rows)
    # require reasonably complete months (>= 20*24 hours)
    mdf = mdf[mdf["n_hours"] >= 480] if len(mdf) else mdf
    label = (
        "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN "
        "(interval-aggregated — NOT utility bills)"
    )
    if len(mdf) == 0:
        return {
            "resolution": "monthly",
            "source_type": "interval_meter_monthly",
            "status": "insufficient_data",
            "n": 0,
            "p": 1,
            "labeled_as_gl14": False,
            "partial_period_monthly_threshold_screen": True,
            "label": label,
        }
    stats = nmbe_cvrmse_pct(mdf["kwh_obs"], mdf["kwh_sim"], p=1)
    return {
        "resolution": "monthly",
        "source_type": "interval_meter_monthly",
        "status": gate_monthly(stats),
        "n": int(stats["n"]),
        "p": 1,
        "nmbe_pct": stats["nmbe_pct"],
        "cvrmse_pct": stats["cvrmse_pct"],
        "mean_obs": stats["mean_obs"],
        "labeled_as_gl14": False,
        "partial_period_monthly_threshold_screen": True,
        "label": label,
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "p_rationale": "p=1 calibrated-sim convention on monthly aggregates of interval kWh",
        "formula": stats.get("formula"),
        "n_months_complete_enough": int(len(mdf)),
        "denominator": "n-p",
    }


def json_load(path: Path) -> dict:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


# Fixed a-priori winter holdout for Lakeside AMY (chosen before examining trial metrics).
# Forward-only policy: train → selection val → locked January → Feb–Mar post-holdout only.
LOCKED_WINTER_HOLDOUT_START = pd.Timestamp("2026-01-01", tz="UTC")
LOCKED_WINTER_HOLDOUT_END = pd.Timestamp("2026-02-01", tz="UTC")
CALIB_END = pd.Timestamp("2025-12-15", tz="UTC")
SELECTION_VAL_END = pd.Timestamp("2026-01-01", tz="UTC")  # Dec 15 → Jan 1 (exclusive)
POST_HOLDOUT_START = pd.Timestamp("2026-02-01", tz="UTC")
POST_HOLDOUT_END = pd.Timestamp("2026-04-01", tz="UTC")


def chronological_splits(
    aligned: pd.DataFrame,
    *,
    ts_col: str = "interval_end_utc",
    require_nonempty: bool = True,
) -> dict[str, Any]:
    """Explicit forward chronological periods — no random split; winter never ranks.

    Locked January cold-month policy (AMY ~ Aug 2025 .. Jul 2026):
      - calibration_development: data start → 2025-12-15
      - chronological_validation: 2025-12-15 → 2026-01-01 (selection only; forward)
      - locked_winter_holdout: 2026-01-01 → 2026-02-01 (champion only, after selection)
      - post_holdout_generalization: 2026-02-01 → 2026-04-01 (never for training/selection)
      - winter_peak_validation: Feb 1–15 diagnostics (subset of post-holdout)
      - annual_summer_generalization: final 30 days (never for ranking)

    Every training timestamp precedes every validation timestamp precedes holdout.
    Not nested chronological CV (no rolling-origin inner folds).
    """
    ts = pd.to_datetime(aligned[ts_col], utc=True)
    if ts.empty:
        raise AlignmentError("chronological_splits: empty aligned series")
    t_min = ts.min()
    t_max = ts.max()
    calib_end = CALIB_END
    val_end = SELECTION_VAL_END
    jan_start = LOCKED_WINTER_HOLDOUT_START
    jan_end = LOCKED_WINTER_HOLDOUT_END
    post_start = POST_HOLDOUT_START
    post_end = POST_HOLDOUT_END
    peak_start = pd.Timestamp("2026-02-01", tz="UTC")
    peak_end = pd.Timestamp("2026-02-15", tz="UTC")
    summer_start = t_max - pd.Timedelta(days=30)

    # Fail loudly if critical forward-policy anchors are outside the data span.
    # post_holdout_end may extend past t_max (partial Feb–Mar still OK).
    required_anchors = {
        "calib_end": calib_end,
        "selection_val_end": val_end,
        "locked_winter_start": jan_start,
        "locked_winter_end": jan_end,
    }
    for name, anchor in required_anchors.items():
        if anchor < t_min or anchor > t_max + pd.Timedelta(hours=1):
            raise AlignmentError(
                f"AMY period anchor {name}={anchor} outside data range "
                f"[{t_min} .. {t_max}]"
            )

    def mask_range(start, end):
        return (ts >= start) & (ts < end)

    # Strict forward order assertions
    if not (t_min < calib_end <= val_end <= jan_start < jan_end <= post_start < post_end):
        raise AlignmentError("chronological period anchors violate forward-time order")

    n_calib = int(mask_range(t_min, calib_end).sum())
    n_val = int(mask_range(calib_end, val_end).sum())
    n_winter = int(mask_range(jan_start, jan_end).sum())
    n_post = int(mask_range(post_start, post_end).sum())
    if require_nonempty:
        for label, n in (
            ("calibration_development", n_calib),
            ("chronological_validation", n_val),
            ("locked_winter_holdout", n_winter),
        ):
            if n <= 0:
                raise AlignmentError(f"chronological period {label} is empty")

    periods = {
        "calibration_development": {
            "start": str(t_min),
            "end": str(calib_end),
            "n": n_calib,
            "role": "tuning_allowed",
        },
        "chronological_validation": {
            "start": str(calib_end),
            "end": str(val_end),
            "segments": [{"start": str(calib_end), "end": str(val_end)}],
            "n": n_val,
            "role": "selection_allowed_not_final",
            "forward_only": True,
            "excludes_post_january": True,
        },
        "winter_peak_validation": {
            "start": str(peak_start),
            "end": str(peak_end),
            "n": int(mask_range(peak_start, peak_end).sum()),
            "role": "peak_diagnostics_not_ranking",
        },
        "locked_winter_holdout": {
            "start": str(jan_start),
            "end": str(jan_end),
            "n": n_winter,
            "role": "locked_no_tuning_evaluate_once",
            "chosen_a_priori": True,
            "rationale": (
                "Full January 2026 locked before any trial ranking; never train/refit "
                "on Feb–Mar before this evaluation"
            ),
        },
        "post_holdout_generalization": {
            "start": str(post_start),
            "end": str(post_end),
            "n": n_post,
            "role": "external_post_holdout_only",
            "note": "Feb–Mar never used for training or candidate selection",
        },
        "annual_summer_generalization": {
            "start": str(summer_start),
            "end": str(t_max),
            "n": int((ts >= summer_start).sum()),
            "role": "generalization_diagnostic_not_ranking",
        },
        # Back-compat alias — explicitly NOT winter
        "locked_final_holdout": {
            "start": str(summer_start),
            "end": str(t_max),
            "n": int((ts >= summer_start).sum()),
            "role": "alias_of_annual_summer_generalization",
            "warning": "Not a winter holdout — use locked_winter_holdout",
        },
        "policy": {
            "name": "forward_january_locked_cold_month_v2",
            "nested_chronological_cv": False,
            "train_before_val_before_holdout": True,
        },
    }
    periods["notes"] = (
        "Rank candidates on chronological_validation (Dec 15–31) hourly (+ monthly gates) only. "
        "Evaluate locked_winter_holdout exactly once after champion selection. "
        "Feb–Mar is post_holdout_generalization only — never train/refit before January eval. "
        "Not nested chronological CV."
    )
    if periods["locked_winter_holdout"]["n"] < 24 * 7:
        periods["limitation"] = (
            "locked_winter_holdout shorter than 7 days of hours — state prominently"
        )
    return periods


def period_mask(
    aligned: pd.DataFrame,
    period_name: str,
    *,
    ts_col: str = "interval_end_utc",
) -> pd.Series:
    """Boolean mask for a named chronological period (no leakage helpers)."""
    ts = pd.to_datetime(aligned[ts_col], utc=True)
    periods = chronological_splits(aligned, ts_col=ts_col, require_nonempty=False)
    if period_name == "chronological_validation":
        segs = periods["chronological_validation"]["segments"]
        mask = pd.Series(False, index=aligned.index)
        for seg in segs:
            start = pd.Timestamp(seg["start"])
            end = pd.Timestamp(seg["end"])
            mask = mask | ((ts >= start) & (ts < end))
        return mask
    if period_name not in periods or not isinstance(periods[period_name], dict):
        raise KeyError(period_name)
    start = pd.Timestamp(periods[period_name]["start"])
    end = pd.Timestamp(periods[period_name]["end"])
    if period_name == "annual_summer_generalization" or period_name == "locked_final_holdout":
        return ts >= start
    return (ts >= start) & (ts < end)


def day_level_peak_metrics(
    aligned: pd.DataFrame,
    *,
    ts_col: str = "interval_end_utc",
    obs_col: str = "observed_kw",
    sim_col: str = "simulated_kw",
    local_tz: str = "America/Chicago",
) -> dict[str, Any]:
    """Per-complete-day peak magnitude/timing (circular hours) — never multi-month argmax."""
    df = aligned.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    local = df[ts_col].dt.tz_convert(local_tz)
    df["local_date"] = local.dt.strftime("%Y-%m-%d")
    df["local_hour"] = local.dt.hour + local.dt.minute / 60.0
    rows: list[dict[str, Any]] = []
    for day, g in df.groupby("local_date"):
        # Complete civil day ≈ 24 hourly points (allow 23–25 for DST)
        if len(g) < 23:
            continue
        yt = g[obs_col].to_numpy(dtype=float)
        yp = g[sim_col].to_numpy(dtype=float)
        hours = g["local_hour"].to_numpy(dtype=float)
        i_obs = int(np.argmax(yt))
        i_sim = int(np.argmax(yp))
        h_obs = float(hours[i_obs])
        h_sim = float(hours[i_sim])
        circ = abs(h_obs - h_sim)
        circ = min(circ, 24.0 - circ)
        morning = g[(g["local_hour"] >= 5.0) & (g["local_hour"] < 9.0)]
        morning_mae = (
            float(np.mean(np.abs(morning[sim_col] - morning[obs_col])))
            if len(morning)
            else None
        )
        rows.append(
            {
                "day": day,
                "measured_peak_kw": float(yt.max()),
                "predicted_peak_kw": float(yp.max()),
                "abs_peak_magnitude_error_kw": float(abs(yt.max() - yp.max())),
                "measured_peak_hour": h_obs,
                "predicted_peak_hour": h_sim,
                "circular_abs_peak_timing_error_h": circ,
                "morning_he05_09_mae_kw": morning_mae,
                "daily_kwh_error": float(yp.sum() - yt.sum()),
                "n_intervals": int(len(g)),
            }
        )
    if not rows:
        return {
            "n_complete_days": 0,
            "status": "insufficient_data",
            "days": [],
            "note": "No complete days for day-level peak metrics",
        }

    def _agg(key: str, *, absolute: bool = False) -> dict[str, float]:
        vals = np.asarray([r[key] for r in rows if r.get(key) is not None], dtype=float)
        if absolute:
            vals = np.abs(vals)
        if len(vals) == 0:
            return {}
        return {
            "median": float(np.median(vals)),
            "mean": float(np.mean(vals)),
            "p90": float(np.percentile(vals, 90)),
            "worst": float(np.max(vals)),
        }

    return {
        "n_complete_days": len(rows),
        "status": "ok",
        "abs_peak_magnitude_error_kw": _agg("abs_peak_magnitude_error_kw"),
        "circular_abs_peak_timing_error_h": _agg("circular_abs_peak_timing_error_h"),
        "morning_he05_09_mae_kw": _agg("morning_he05_09_mae_kw"),
        "daily_kwh_error_abs": _agg("daily_kwh_error", absolute=True),
        "days": rows,
        "forbidden_metric": "multi_month_global_argmax_timing_hours",
        "note": "Peak timing is circular hours within each civil day — never multi-month argmax",
    }


def score_period(
    aligned: pd.DataFrame,
    period_name: str,
    *,
    resolution: str = "hourly",
    ts_col: str = "interval_end_utc",
) -> dict[str, Any] | None:
    mask = period_mask(aligned, period_name, ts_col=ts_col)
    sub = aligned.loc[mask]
    if len(sub) < 24:
        return {
            "resolution": resolution,
            "period": period_name,
            "status": "insufficient_data",
            "n": int(len(sub)),
            "p": 1,
        }
    block = score_aligned(sub, resolution=resolution)
    block["period"] = period_name
    return block


# ---------------------------------------------------------------------------
# W2A integrity closure — rolling-origin selection (Nov–Dec only); Jan consumed
# ---------------------------------------------------------------------------
# Prior IdealLoads January locked holdout is CONSUMED for this building/family
# and must not be treated as pristine for W2A selection ranking.
JANUARY_HOLDOUT_CONSUMED = True
JANUARY_HOLDOUT_NOTE = (
    "IdealLoads January 2026 locked holdout was consumed during prior schedule/"
    "plant-proxy work for this building family — not pristine for W2A selection."
)

# Predeclared exploratory selection folds (local America/Chicago civil dates).
# Score the next `horizon_days` local days after each origin (exclusive of training
# through origin). Reserved final winter audit is February local month — never
# fed back into ranking.
ROLLING_ORIGIN_SELECTION_FOLDS: list[dict[str, Any]] = [
    {"origin_local": "2025-11-15", "horizon_days": 10, "fold_id": "ro_nov15"},
    {"origin_local": "2025-11-30", "horizon_days": 10, "fold_id": "ro_nov30"},
    {"origin_local": "2025-12-15", "horizon_days": 10, "fold_id": "ro_dec15"},
]
RESERVED_FINAL_WINTER_AUDIT = {
    "period_id": "reserved_final_winter_audit",
    "local_month": "2026-02",
    "tz": "America/Chicago",
    "role": "evaluate_once_after_selection_never_rank",
}


def rolling_origin_selection_mask(
    aligned: pd.DataFrame,
    *,
    origin_local: str,
    horizon_days: int = 10,
    ts_col: str = "interval_end_utc",
    local_tz: str = "America/Chicago",
) -> pd.Series:
    """Mask for the score window: local days (origin, origin+horizon].

    Training-through-origin is implied for documentation only; this mask is the
    held-forward score slice used for exploratory ranking.
    """
    ts = pd.to_datetime(aligned[ts_col], utc=True)
    local = ts.dt.tz_convert(local_tz)
    origin = pd.Timestamp(origin_local, tz=local_tz)
    end = origin + pd.Timedelta(days=int(horizon_days))
    return (local > origin) & (local <= end)


def reserved_final_winter_audit_mask(
    aligned: pd.DataFrame,
    *,
    ts_col: str = "interval_end_utc",
    local_tz: str = "America/Chicago",
    local_month: str = "2026-02",
) -> pd.Series:
    """February local month — reserved final audit; never used for selection."""
    ts = pd.to_datetime(aligned[ts_col], utc=True)
    local = ts.dt.tz_convert(local_tz)
    year_s, month_s = local_month.split("-")
    year, month = int(year_s), int(month_s)
    return (local.dt.year == year) & (local.dt.month == month)


def score_rolling_origin_selection(
    aligned: pd.DataFrame,
    *,
    folds: list[dict[str, Any]] | None = None,
    ts_col: str = "interval_end_utc",
    obs_col: str = "observed_kw",
    sim_col: str = "simulated_kw",
) -> dict[str, Any]:
    """Median fold CVRMSE on Nov–Dec rolling origins only (exploratory ranking)."""
    folds = folds or ROLLING_ORIGIN_SELECTION_FOLDS
    fold_scores: list[dict[str, Any]] = []
    cvs: list[float] = []
    for fold in folds:
        mask = rolling_origin_selection_mask(
            aligned,
            origin_local=str(fold["origin_local"]),
            horizon_days=int(fold.get("horizon_days", 10)),
            ts_col=ts_col,
        )
        # Guard: never include reserved February in selection
        feb = reserved_final_winter_audit_mask(aligned, ts_col=ts_col)
        if bool((mask & feb).any()):
            raise AlignmentError("rolling-origin selection mask leaked into reserved February")
        sub = aligned.loc[mask]
        if len(sub) < 24:
            fold_scores.append(
                {
                    "fold_id": fold.get("fold_id"),
                    "status": "insufficient_data",
                    "n": int(len(sub)),
                }
            )
            continue
        # score_aligned expects observed_kw / simulated_kw
        work = sub
        if obs_col != "observed_kw" or sim_col != "simulated_kw":
            work = sub.rename(columns={obs_col: "observed_kw", sim_col: "simulated_kw"})
        block = score_aligned(work, resolution="hourly")
        cv = block.get("cvrmse_pct")
        if cv is not None:
            cvs.append(float(cv))
        fold_scores.append(
            {
                "fold_id": fold.get("fold_id"),
                "origin_local": fold.get("origin_local"),
                "horizon_days": fold.get("horizon_days"),
                "n": int(len(sub)),
                "cvrmse_pct": cv,
                "nmbe_pct": block.get("nmbe_pct"),
                "status": "ok",
            }
        )
    median_cv = float(np.median(cvs)) if cvs else None
    return {
        "role": "exploratory_selection_only",
        "january_holdout_consumed": JANUARY_HOLDOUT_CONSUMED,
        "january_holdout_note": JANUARY_HOLDOUT_NOTE,
        "folds": fold_scores,
        "median_fold_cvrmse_pct": median_cv,
        "selection_score": median_cv,  # lower is better
        "excludes_reserved_february": True,
        "excludes_january_from_ranking": True,
    }


def score_reserved_final_winter_audit(
    aligned: pd.DataFrame,
    *,
    ts_col: str = "interval_end_utc",
) -> dict[str, Any]:
    """Evaluate February once after selection — never feed into ranking."""
    mask = reserved_final_winter_audit_mask(aligned, ts_col=ts_col)
    sub = aligned.loc[mask]
    out: dict[str, Any] = {
        **RESERVED_FINAL_WINTER_AUDIT,
        "n": int(len(sub)),
        "used_for_selection": False,
    }
    if len(sub) < 24:
        out["status"] = "insufficient_data"
        return out
    block = score_aligned(sub, resolution="hourly")
    peaks = day_level_peak_metrics(sub, ts_col=ts_col)
    out.update(
        {
            "status": "ok",
            "hourly_score": block,
            "day_level_peaks": {
                k: peaks.get(k)
                for k in (
                    "n_complete_days",
                    "status",
                    "abs_peak_magnitude_error_kw",
                    "circular_abs_peak_timing_error_h",
                    "morning_he05_09_mae_kw",
                )
            },
        }
    )
    return out
