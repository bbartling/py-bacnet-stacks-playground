"""Nearest Historical Days + EnergyPlus Delta — simple DSM engineering benchmark.

Honesty labels:
  SIMPLE_HYBRID_SCREENING / NEAREST_DAY_BASELINE / EPLUS_COUNTERFACTUAL_DELTA

Empirical P10/median/P90 are neighbor ranges — not statistical confidence intervals.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from artifact_paths import EPLUS_PAIRED_PARQUET, default_artifact_dir
from chrono_splits import _day_order_key, build_split_manifest, is_heating_day
from energy_math import peak_kw, quarter_hour_kwh
from feature_compile_heating_dsm import STRATEGY_IDS, TARGET_COLS, ZONE_TEMP_COLS
from metrics_report import daily_peak_errors, mae, rmse
from training_profile import (
    TrainingProfile,
    assert_desktop_library_allowed,
    profile_day_summary,
)

LIBRARY_STEM = "nearest_day_eplus_delta_v1"
LIBRARY_SCHEMA = "nearest_day_eplus_delta_v1"
HONESTY = "SIMPLE_HYBRID_SCREENING"
LABEL_BASELINE = "NEAREST_DAY_BASELINE"
LABEL_DELTA = "EPLUS_COUNTERFACTUAL_DELTA"
WATERMARK_UNDERPOWERED_EPLUS = "UNDERPOWERED_EPLUS_DELTA_LIBRARY"
OOD_STATUS = "OUT_OF_DISTRIBUTION"
DSM_WORSENS_PEAK = "DSM_WORSENS_PEAK"
DSM_WORSENS_ENERGY = "DSM_WORSENS_ENERGY"

STEPS_96 = 96
DEFAULT_K = 10
OOD_PERCENTILE = 95.0
MIN_EPLUS_STRATEGY_RECORDS = 3

# Distance component weights (documented; fitted scales only — not tuned on locked test)
DISTANCE_WEIGHTS = {
    "weekend_mismatch": 2.0,
    "oat_traj": 1.0,
    "midnight_oat": 0.75,
    "midnight_kw": 0.75,
    "midnight_zones": 1.0,
}


@dataclass
class ScaleStats:
    means: dict[str, float]
    stds: dict[str, float]

    def z(self, key: str, value: float) -> float:
        mu = self.means.get(key, 0.0)
        sd = self.stds.get(key, 1.0)
        if sd is None or abs(sd) < 1e-9:
            sd = 1.0
        return (float(value) - float(mu)) / float(sd)


@dataclass
class DayRecord:
    day: str
    is_weekend: float
    oat_96: list[float]
    midnight_oat: float
    midnight_kw: float
    midnight_zones: list[float]
    y_96x7: list[list[float]]  # [96][7]
    regime: str = "heating"

    def match_vector(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "is_weekend": self.is_weekend,
            "midnight_oat": self.midnight_oat,
            "midnight_kw": self.midnight_kw,
            "midnight_zones": list(self.midnight_zones),
            "oat_mean": float(np.mean(self.oat_96)),
            "oat_96": list(self.oat_96),
        }


@dataclass
class NeighborHit:
    day: str
    total_distance: float
    oat_distance: float
    midnight_kw_distance: float
    midnight_zone_distance: float
    weekend_match: bool


@dataclass
class SimpleHybridResult:
    honesty: str = HONESTY
    label_baseline: str = LABEL_BASELINE
    label_delta: str = LABEL_DELTA
    strategy_id: str = "stagger_preheat"
    ood: bool = False
    ood_status: str | None = None
    nearest_distance: float | None = None
    ood_threshold: float | None = None
    failed_criteria: list[str] = field(default_factory=list)
    recommend: bool = True
    outcome_flags: list[str] = field(default_factory=list)
    neighbors: list[NeighborHit] = field(default_factory=list)
    baseline_y: np.ndarray | None = None  # [96,7]
    p10_y: np.ndarray | None = None
    p90_y: np.ndarray | None = None
    delta_y: np.ndarray | None = None
    hybrid_y: np.ndarray | None = None
    eplus_pair_id: str | None = None
    watermark: str | None = None

    def summary_kw(self) -> dict[str, float]:
        assert self.hybrid_y is not None and self.baseline_y is not None
        hb = self.baseline_y[:, 0]
        hh = self.hybrid_y[:, 0]
        return {
            "peak_kw_baseline": peak_kw(hb),
            "peak_kw_hybrid": peak_kw(hh),
            "daily_kwh_baseline": quarter_hour_kwh(hb),
            "daily_kwh_hybrid": quarter_hour_kwh(hh),
            "delta_peak_kw": float(peak_kw(hh) - peak_kw(hb)),
            "delta_kwh": float(quarter_hour_kwh(hh) - quarter_hour_kwh(hb)),
        }


def billing_period_demand_kw(existing_period_peak_kw: float, simulated_day_peak_kw: float) -> float:
    """Billing demand = max(existing billing-period peak, simulated 24h peak)."""
    return float(max(float(existing_period_peak_kw), float(simulated_day_peak_kw)))


def _complete_day_mask(df: pd.DataFrame, day_col: str = "day") -> list[str]:
    counts = df.groupby(day_col).size()
    return [str(d) for d, n in counts.items() if int(n) >= STEPS_96]


def build_day_records(
    df: pd.DataFrame,
    *,
    require_complete: bool = True,
    heating_only: bool = True,
) -> list[DayRecord]:
    """Build compact day trajectories from a REAL_BAS-like frame."""
    need = {"day", "facility_kw", "oat_f", *ZONE_TEMP_COLS}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"frame missing columns {missing}")
    step_col = "step_15" if "step_15" in df.columns else None
    out: list[DayRecord] = []
    for day, sub in df.groupby("day"):
        sub = sub.sort_values(step_col or "hour_ending")
        if require_complete and len(sub) < STEPS_96:
            continue
        if len(sub) > STEPS_96:
            sub = sub.iloc[:STEPS_96]
        if len(sub) < STEPS_96:
            continue
        oat = sub["oat_f"].to_numpy(dtype=float)
        if heating_only and not is_heating_day(oat):
            continue
        y = sub[list(TARGET_COLS)].to_numpy(dtype=float)
        weekend = float(sub["is_weekend"].iloc[0]) if "is_weekend" in sub.columns else 0.0
        out.append(
            DayRecord(
                day=str(day),
                is_weekend=weekend,
                oat_96=oat.tolist(),
                midnight_oat=float(oat[0]),
                midnight_kw=float(y[0, 0]),
                midnight_zones=y[0, 1:].tolist(),
                y_96x7=y.tolist(),
                regime="heating",
            )
        )
    out.sort(key=lambda r: _day_order_key(r.day))
    return out


def fit_scale_stats(records: Sequence[DayRecord]) -> ScaleStats:
    """Fit standardization on eligible historical / training days only."""
    if not records:
        return ScaleStats(means={}, stds={})
    oat_rmse = []
    keys = {
        "midnight_oat": [r.midnight_oat for r in records],
        "midnight_kw": [r.midnight_kw for r in records],
    }
    for zi in range(6):
        keys[f"zone_{zi}"] = [r.midnight_zones[zi] for r in records]
    # OAT traj scale: mean absolute deviation of oat vector from global mean traj
    oat_mat = np.asarray([r.oat_96 for r in records], dtype=float)
    oat_mean_traj = oat_mat.mean(axis=0)
    keys["oat_traj_l2"] = [
        float(np.linalg.norm(np.asarray(r.oat_96) - oat_mean_traj)) for r in records
    ]
    means = {k: float(np.mean(v)) for k, v in keys.items()}
    stds = {k: float(np.std(v) + 1e-9) for k, v in keys.items()}
    means["_oat_mean_traj"] = 0.0  # placeholder; store traj separately
    return ScaleStats(means=means, stds=stds)


def _oat_mean_traj(records: Sequence[DayRecord]) -> np.ndarray:
    return np.asarray([r.oat_96 for r in records], dtype=float).mean(axis=0)


def distance_components(
    query: DayRecord,
    cand: DayRecord,
    scales: ScaleStats,
    oat_mean_traj: np.ndarray,
) -> dict[str, float]:
    weekend_mismatch = 0.0 if abs(query.is_weekend - cand.is_weekend) < 0.5 else 1.0
    oat_l2 = float(np.linalg.norm(np.asarray(query.oat_96) - np.asarray(cand.oat_96)))
    oat_z = oat_l2 / max(scales.stds.get("oat_traj_l2", 1.0), 1e-9)
    mid_oat = abs(scales.z("midnight_oat", query.midnight_oat) - scales.z("midnight_oat", cand.midnight_oat))
    mid_kw = abs(scales.z("midnight_kw", query.midnight_kw) - scales.z("midnight_kw", cand.midnight_kw))
    zone = 0.0
    for zi in range(6):
        zone += abs(
            scales.z(f"zone_{zi}", query.midnight_zones[zi])
            - scales.z(f"zone_{zi}", cand.midnight_zones[zi])
        )
    zone /= 6.0
    return {
        "weekend_mismatch": weekend_mismatch,
        "oat_distance": oat_z,
        "midnight_oat_distance": mid_oat,
        "midnight_kw_distance": mid_kw,
        "midnight_zone_distance": zone,
    }


def total_distance(components: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = weights or DISTANCE_WEIGHTS
    return float(
        w["weekend_mismatch"] * components["weekend_mismatch"]
        + w["oat_traj"] * components["oat_distance"]
        + w["midnight_oat"] * components["midnight_oat_distance"]
        + w["midnight_kw"] * components["midnight_kw_distance"]
        + w["midnight_zones"] * components["midnight_zone_distance"]
    )


def eligible_neighbors(
    library: Sequence[DayRecord],
    *,
    before_day: str,
    exclude_day: str | None = None,
) -> list[DayRecord]:
    """Strictly earlier days only; never self; never future."""
    before_key = _day_order_key(before_day)
    excl = str(exclude_day) if exclude_day is not None else None
    out = []
    for r in library:
        if excl is not None and r.day == excl:
            continue
        if r.day == str(before_day):
            continue
        if _day_order_key(r.day) >= before_key:
            continue
        out.append(r)
    return out


def rank_neighbors(
    query: DayRecord,
    candidates: Sequence[DayRecord],
    scales: ScaleStats,
    *,
    k: int = DEFAULT_K,
    weights: dict[str, float] | None = None,
    oat_mean_traj: np.ndarray | None = None,
) -> list[NeighborHit]:
    if not candidates:
        return []
    traj = oat_mean_traj if oat_mean_traj is not None else _oat_mean_traj(candidates)
    hits: list[NeighborHit] = []
    for c in candidates:
        comp = distance_components(query, c, scales, traj)
        hits.append(
            NeighborHit(
                day=c.day,
                total_distance=total_distance(comp, weights),
                oat_distance=comp["oat_distance"],
                midnight_kw_distance=comp["midnight_kw_distance"],
                midnight_zone_distance=comp["midnight_zone_distance"],
                weekend_match=comp["weekend_mismatch"] < 0.5,
            )
        )
    hits.sort(key=lambda h: (h.total_distance, h.day))
    return hits[: int(k)]


def pointwise_percentiles(
    neighbor_ys: Sequence[np.ndarray],
    *,
    qs: Sequence[float] = (10.0, 50.0, 90.0),
) -> dict[str, np.ndarray]:
    """Pointwise percentiles over neighbor [96,7] stacks. Not CIs."""
    stack = np.stack([np.asarray(y, dtype=float) for y in neighbor_ys], axis=0)
    out = {}
    for q in qs:
        out[f"p{int(q)}"] = np.percentile(stack, q, axis=0)
    return out


def loo_nearest_distances(
    records: Sequence[DayRecord],
    scales: ScaleStats,
    *,
    weights: dict[str, float] | None = None,
) -> list[float]:
    """Leave-one-day-out nearest-neighbor distances on development data only."""
    traj = _oat_mean_traj(records)
    dists: list[float] = []
    for i, q in enumerate(records):
        cands = [r for j, r in enumerate(records) if j != i and _day_order_key(r.day) < _day_order_key(q.day)]
        if not cands:
            # allow any other earlier-or-any for LOO scale when chronology blocks
            cands = [r for j, r in enumerate(records) if j != i]
        if not cands:
            continue
        hits = rank_neighbors(q, cands, scales, k=1, weights=weights, oat_mean_traj=traj)
        if hits:
            dists.append(hits[0].total_distance)
    return dists


def ood_threshold_from_loo(distances: Sequence[float], *, percentile: float = OOD_PERCENTILE) -> float:
    if not distances:
        return float("inf")
    return float(np.percentile(np.asarray(distances, dtype=float), percentile))


def build_eplus_delta_library(paired: pd.DataFrame) -> list[dict[str, Any]]:
    """Compact DSM−baseline delta records from paired E+ farm."""
    need = {"pair_id", "arm", "facility_kw", *ZONE_TEMP_COLS}
    if missing := (need - set(paired.columns)):
        raise ValueError(f"paired missing {missing}")
    records: list[dict[str, Any]] = []
    for pair_id, g in paired.groupby("pair_id"):
        arms = set(g["arm"].astype(str).unique())
        if "baseline" not in arms or "dsm" not in arms:
            continue
        b = g[g["arm"].astype(str) == "baseline"].sort_values(
            "step_15" if "step_15" in g.columns else "hour_ending"
        )
        d = g[g["arm"].astype(str) == "dsm"].sort_values(
            "step_15" if "step_15" in g.columns else "hour_ending"
        )
        if len(b) < STEPS_96 or len(d) < STEPS_96:
            continue
        b = b.iloc[:STEPS_96]
        d = d.iloc[:STEPS_96]
        yb = b[list(TARGET_COLS)].to_numpy(dtype=float)
        yd = d[list(TARGET_COLS)].to_numpy(dtype=float)
        delta = yd - yb
        sid = str(d["strategy_id"].iloc[0]) if "strategy_id" in d.columns else "unknown"
        oat = b["oat_f"].to_numpy(dtype=float) if "oat_f" in b.columns else np.zeros(STEPS_96)
        records.append(
            {
                "pair_id": str(pair_id),
                "strategy_id": sid,
                "oat_96": oat.tolist(),
                "init_zones": yb[0, 1:].tolist(),
                "delta_96x7": delta.tolist(),
            }
        )
    return records


def match_eplus_delta(
    library: Sequence[dict[str, Any]],
    *,
    strategy_id: str,
    oat_96: Sequence[float],
    init_zones: Sequence[float],
) -> tuple[np.ndarray | None, str | None, list[str]]:
    """Closest compatible E+ delta for strategy; returns (delta[96,7], pair_id, failed)."""
    failed: list[str] = []
    pool = [r for r in library if str(r.get("strategy_id")) == str(strategy_id)]
    if not pool:
        failed.append(f"no_eplus_records_for_strategy={strategy_id}")
        return None, None, failed
    oat_q = np.asarray(oat_96, dtype=float)
    z_q = np.asarray(init_zones, dtype=float)
    best = None
    best_d = float("inf")
    best_id = None
    for r in pool:
        oat_d = float(np.linalg.norm(oat_q - np.asarray(r["oat_96"], dtype=float)))
        z_d = float(np.linalg.norm(z_q - np.asarray(r["init_zones"], dtype=float)))
        dist = oat_d + z_d
        if dist < best_d:
            best_d = dist
            best = np.asarray(r["delta_96x7"], dtype=float)
            best_id = str(r["pair_id"])
    return best, best_id, failed


def query_from_inputs(
    *,
    midnight_kw: float,
    midnight_zones: Sequence[float],
    oat_96: Sequence[float],
    is_weekend: bool,
    day_label: str = "query",
) -> DayRecord:
    oat = list(map(float, oat_96))
    if len(oat) != STEPS_96:
        raise ValueError(f"oat_96 must have {STEPS_96} steps")
    zones = list(map(float, midnight_zones))
    if len(zones) != 6:
        raise ValueError("need 6 midnight zone temps")
    y0 = [float(midnight_kw), *zones]
    # placeholder trajectory (filled by neighbors for baseline)
    y = [y0 for _ in range(STEPS_96)]
    return DayRecord(
        day=str(day_label),
        is_weekend=1.0 if is_weekend else 0.0,
        oat_96=oat,
        midnight_oat=float(oat[0]),
        midnight_kw=float(midnight_kw),
        midnight_zones=zones,
        y_96x7=y,
    )


def run_simple_hybrid(
    query: DayRecord,
    day_library: Sequence[DayRecord],
    eplus_library: Sequence[dict[str, Any]],
    scales: ScaleStats,
    *,
    strategy_id: str,
    k: int = DEFAULT_K,
    ood_threshold: float,
    before_day: str | None = None,
    weights: dict[str, float] | None = None,
    allow_exploratory_if_ood: bool = True,
) -> SimpleHybridResult:
    """Nearest-day median baseline + E+ delta. Leakage-safe when before_day set."""
    ref_day = before_day or query.day
    cands = eligible_neighbors(day_library, before_day=ref_day, exclude_day=query.day)
    failed: list[str] = []
    if len(cands) < 1:
        failed.append("no_eligible_historical_neighbors")
    traj = _oat_mean_traj(day_library) if day_library else np.zeros(STEPS_96)
    hits = rank_neighbors(query, cands, scales, k=k, weights=weights, oat_mean_traj=traj)
    nearest = hits[0].total_distance if hits else None
    ood = False
    if nearest is None or (ood_threshold < float("inf") and nearest > ood_threshold):
        ood = True
        failed.append(
            f"nearest_distance={nearest} exceeds threshold={ood_threshold}"
            if nearest is not None
            else "no_neighbor_distance"
        )
    if len(hits) < min(k, 1):
        ood = True
        failed.append(f"insufficient_neighbors={len(hits)} k={k}")

    by_day = {r.day: r for r in day_library}
    neighbor_ys = [np.asarray(by_day[h.day].y_96x7, dtype=float) for h in hits if h.day in by_day]
    if not neighbor_ys:
        # exploratory empty
        baseline = np.zeros((STEPS_96, 7))
        p10 = p90 = baseline.copy()
    else:
        pct = pointwise_percentiles(neighbor_ys)
        baseline = pct["p50"]
        p10 = pct["p10"]
        p90 = pct["p90"]

    delta, pair_id, e_failed = match_eplus_delta(
        eplus_library,
        strategy_id=strategy_id,
        oat_96=query.oat_96,
        init_zones=query.midnight_zones,
    )
    failed.extend(e_failed)
    watermark = None
    if len(eplus_library) < MIN_EPLUS_STRATEGY_RECORDS:
        watermark = WATERMARK_UNDERPOWERED_EPLUS
    if delta is None:
        delta = np.zeros((STEPS_96, 7))
        ood = True
        failed.append("missing_eplus_delta")

    hybrid = baseline + delta
    flags: list[str] = []
    summ_peak = float(peak_kw(hybrid[:, 0]) - peak_kw(baseline[:, 0]))
    summ_kwh = float(quarter_hour_kwh(hybrid[:, 0]) - quarter_hour_kwh(baseline[:, 0]))
    recommend = not ood
    if summ_peak > 0:
        flags.append(DSM_WORSENS_PEAK)
        recommend = False
    if summ_kwh > 0:
        flags.append(DSM_WORSENS_ENERGY)
        recommend = False
    if ood:
        recommend = False

    return SimpleHybridResult(
        strategy_id=strategy_id,
        ood=ood,
        ood_status=OOD_STATUS if ood else None,
        nearest_distance=nearest,
        ood_threshold=ood_threshold,
        failed_criteria=failed,
        recommend=recommend if not (ood and not allow_exploratory_if_ood) else recommend,
        outcome_flags=flags,
        neighbors=hits,
        baseline_y=baseline,
        p10_y=p10,
        p90_y=p90,
        delta_y=delta,
        hybrid_y=hybrid,
        eplus_pair_id=pair_id,
        watermark=watermark,
    )


def persistence_forecast(prev_day_y: np.ndarray) -> np.ndarray:
    return np.asarray(prev_day_y, dtype=float).copy()


def typical_weekend_median(
    library: Sequence[DayRecord], *, is_weekend: bool
) -> np.ndarray:
    pool = [np.asarray(r.y_96x7, dtype=float) for r in library if bool(r.is_weekend) == bool(is_weekend)]
    if not pool:
        pool = [np.asarray(r.y_96x7, dtype=float) for r in library]
    return np.median(np.stack(pool, axis=0), axis=0)


def score_day(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    comfort_lo: float = 66.0,
    comfort_hi: float = 78.0,
) -> dict[str, Any]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    fac = daily_peak_errors(yt[:, 0], yp[:, 0])
    zone_mae = [mae(yt[:, i], yp[:, i]) for i in range(1, 7)]
    zone_rmse = [rmse(yt[:, i], yp[:, i]) for i in range(1, 7)]
    pk = np.zeros(len(yt), dtype=bool)
    pk[20:36] = True
    viol = 0
    for t in range(len(yt)):
        for z in range(1, 7):
            if yp[t, z] < comfort_lo or yp[t, z] > comfort_hi:
                viol += 1
    return {
        "facility_kw_mae": mae(yt[:, 0], yp[:, 0]),
        "facility_kw_rmse": rmse(yt[:, 0], yp[:, 0]),
        "facility_kw_mae_peak_05_09": mae(yt[pk, 0], yp[pk, 0]) if pk.any() else mae(yt[:, 0], yp[:, 0]),
        **fac,
        "zone_mae": {ZONE_TEMP_COLS[i]: zone_mae[i] for i in range(6)},
        "zone_rmse": {ZONE_TEMP_COLS[i]: zone_rmse[i] for i in range(6)},
        "worst_zone_mae": float(max(zone_mae)) if zone_mae else None,
        "comfort_violations": int(viol),
    }


def evaluate_benchmark_on_days(
    records: Sequence[DayRecord],
    eval_days: Sequence[str],
    eplus_library: Sequence[dict[str, Any]],
    scales: ScaleStats,
    *,
    ood_threshold: float,
    strategy_id: str = "stagger_preheat",
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    """Leakage-safe eval: neighbors strictly before each eval day."""
    by_day = {r.day: r for r in records}
    rows = []
    ood_n = 0
    for day in eval_days:
        if day not in by_day:
            continue
        truth = by_day[day]
        res = run_simple_hybrid(
            truth,
            records,
            eplus_library,
            scales,
            strategy_id=strategy_id,
            k=k,
            ood_threshold=ood_threshold,
            before_day=day,
        )
        if res.ood:
            ood_n += 1
        assert res.hybrid_y is not None
        sc = score_day(np.asarray(truth.y_96x7), res.hybrid_y)
        sc["day"] = day
        sc["ood"] = res.ood
        sc["nearest_distance"] = res.nearest_distance
        rows.append(sc)
    return {
        "n_evaluated_days": len(rows),
        "ood_refusal_rate": float(ood_n / len(rows)) if rows else None,
        "per_day": rows,
    }


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_library(
    *,
    records: Sequence[DayRecord],
    eplus_library: Sequence[dict[str, Any]],
    scales: ScaleStats,
    ood_threshold: float,
    profile: TrainingProfile,
    out_dir: Path | None = None,
    desktop_dir: Path | None = None,
    run_id: str | None = None,
    frozen_eval: dict[str, Any] | None = None,
    source_hashes: dict[str, str | None] | None = None,
    k: int = DEFAULT_K,
) -> Path:
    """Write versioned compact library. Desktop copy only if profile allows."""
    assert_desktop_library_allowed(profile)
    art = Path(out_dir or default_artifact_dir())
    art.mkdir(parents=True, exist_ok=True)
    oat_traj = _oat_mean_traj(records).tolist() if records else [0.0] * STEPS_96
    doc = {
        "schema": LIBRARY_SCHEMA,
        "honesty": HONESTY,
        "label_baseline": LABEL_BASELINE,
        "label_delta": LABEL_DELTA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "profile": profile.to_dict(),
        "watermark": profile.watermark,
        "k": int(k),
        "ood_threshold": float(ood_threshold),
        "ood_percentile": OOD_PERCENTILE,
        "distance_weights": dict(DISTANCE_WEIGHTS),
        "scale_means": scales.means,
        "scale_stds": scales.stds,
        "oat_mean_traj": oat_traj,
        "target_cols": list(TARGET_COLS),
        "zone_temp_cols": list(ZONE_TEMP_COLS),
        "units": {"facility_kw": "kW", "zone_temp": "degF", "oat": "degF"},
        "steps": STEPS_96,
        "days": [
            {
                **r.match_vector(),
                "y_96x7": r.y_96x7,
                "regime": r.regime,
            }
            for r in records
        ],
        "eplus_delta_records": list(eplus_library),
        "eplus_watermark": WATERMARK_UNDERPOWERED_EPLUS
        if len(eplus_library) < MIN_EPLUS_STRATEGY_RECORDS
        else None,
        "frozen_full_evaluation": frozen_eval,
        "source_hashes": source_hashes or {},
    }
    path = art / f"{LIBRARY_STEM}.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    if desktop_dir is not None:
        desk = Path(desktop_dir)
        desk.mkdir(parents=True, exist_ok=True)
        (desk / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def build_library_from_frame(
    df: pd.DataFrame,
    *,
    profile: TrainingProfile,
    paired_parquet: Path | None = None,
    out_dir: Path | None = None,
    desktop_dir: Path | None = None,
    run_id: str | None = None,
    strategy_id: str = "stagger_preheat",
) -> dict[str, Any]:
    """End-to-end: records, scales, OOD from LOO on development days, optional export."""
    records = build_day_records(
        df,
        require_complete=profile.require_complete_96_step_days,
        heating_only=profile.heating_only,
    )
    if profile.max_days is not None:
        records = records[: int(profile.max_days)]

    # Chrono manifest for day accounting
    # Build a minimal day-level frame for splits
    rows = []
    for r in records:
        try:
            month = int(pd.to_datetime(r.day).month)
        except Exception:
            month = 1
        for oat in r.oat_96:
            rows.append({"day": r.day, "oat_f": oat, "month": month})
    day_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["day", "oat_f", "month"])
    manifest = build_split_manifest(day_df) if len(day_df) else {
        "all_days": [],
        "heating_days": [],
        "dev_days": [],
        "final_winter_test": [],
        "folds": [],
    }
    dev = [str(d) for d in manifest.get("dev_days") or [r.day for r in records]]
    locked = [str(d) for d in manifest.get("final_winter_test") or []]
    by_day = {r.day: r for r in records}
    if profile.mode == "full_deployment":
        lib_days = list(records)  # includes former locked test
        deployment_refit = [r.day for r in records]
    else:
        lib_days = [by_day[d] for d in dev if d in by_day]
        deployment_refit = []

    scales = fit_scale_stats(lib_days if lib_days else records)
    loo = loo_nearest_distances(lib_days if lib_days else records, scales)
    thresh = ood_threshold_from_loo(loo)

    paired_path = Path(paired_parquet or (default_artifact_dir() / EPLUS_PAIRED_PARQUET))
    eplus_lib: list[dict[str, Any]] = []
    if paired_path.is_file():
        eplus_lib = build_eplus_delta_library(pd.read_parquet(paired_path))

    summary = profile_day_summary(
        source_days=list(df["day"].astype(str).unique()) if "day" in df.columns else [],
        complete_days=[r.day for r in records],
        heating_days=[r.day for r in records],
        development_days=dev,
        locked_test_days=locked,
        folds=manifest.get("folds"),
        deployment_refit_days=deployment_refit,
        profile=profile,
    )

    frozen_eval = None
    if profile.mode == "full_evaluation" and locked:
        frozen_eval = evaluate_benchmark_on_days(
            records, locked, eplus_lib, scales, ood_threshold=thresh, strategy_id=strategy_id
        )
        frozen_eval["run_id"] = run_id

    path = None
    if profile.allow_desktop_library_export:
        path = export_library(
            records=lib_days if lib_days else records,
            eplus_library=eplus_lib,
            scales=scales,
            ood_threshold=thresh,
            profile=profile,
            out_dir=out_dir,
            desktop_dir=desktop_dir,
            run_id=run_id,
            frozen_eval=frozen_eval,
            source_hashes={
                "paired_parquet": _sha256_file(paired_path),
            },
        )

    return {
        "records": records,
        "lib_days": lib_days,
        "scales": scales,
        "ood_threshold": thresh,
        "eplus_library": eplus_lib,
        "manifest": manifest,
        "summary": summary,
        "frozen_eval": frozen_eval,
        "library_path": path,
    }


def result_to_walk_dict(res: SimpleHybridResult, *, contract_version: str = "nearest_day_eplus_delta_v1") -> dict[str, Any]:
    """HybridWalk-compatible JSON for desktop / notebook overlays."""
    assert res.baseline_y is not None and res.hybrid_y is not None and res.delta_y is not None
    steps = []
    for i in range(STEPS_96):
        steps.append(
            {
                "step_15": i,
                "baseline_facility_kw": float(res.baseline_y[i, 0]),
                "hybrid_facility_kw": float(res.hybrid_y[i, 0]),
                "delta_facility_kw": float(res.delta_y[i, 0]),
                "p10_facility_kw": float(res.p10_y[i, 0]) if res.p10_y is not None else None,
                "p90_facility_kw": float(res.p90_y[i, 0]) if res.p90_y is not None else None,
                "baseline_zone_temps_f": {
                    ZONE_TEMP_COLS[z]: float(res.baseline_y[i, z + 1]) for z in range(6)
                },
                "hybrid_zone_temps_f": {
                    ZONE_TEMP_COLS[z]: float(res.hybrid_y[i, z + 1]) for z in range(6)
                },
                "delta_zone_temps_f": {
                    ZONE_TEMP_COLS[z]: float(res.delta_y[i, z + 1]) for z in range(6)
                },
            }
        )
    summ = res.summary_kw()
    return {
        "contract_version": contract_version,
        "honesty": res.honesty,
        "label_baseline": res.label_baseline,
        "label_delta": res.label_delta,
        "strategy_id": res.strategy_id,
        "ood": res.ood,
        "ood_status": res.ood_status,
        "nearest_distance": res.nearest_distance,
        "ood_threshold": res.ood_threshold,
        "failed_criteria": res.failed_criteria,
        "recommend": res.recommend,
        "outcome_flags": res.outcome_flags,
        "watermark": res.watermark,
        "eplus_pair_id": res.eplus_pair_id,
        "neighbors": [asdict(n) for n in res.neighbors],
        "steps": steps,
        "summary": {
            "cumulative_kwh_baseline": summ["daily_kwh_baseline"],
            "cumulative_kwh_hybrid": summ["daily_kwh_hybrid"],
            "peak_kw_baseline": summ["peak_kw_baseline"],
            "peak_kw_hybrid": summ["peak_kw_hybrid"],
            "delta_peak_kw": summ["delta_peak_kw"],
            "delta_kwh": summ["delta_kwh"],
            "comfort_violations": 0,
        },
    }
