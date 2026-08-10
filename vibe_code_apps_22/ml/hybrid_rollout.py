"""Hybrid 96-step rollout: real baseline + E+ delta → DSM trajectory."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from feature_compile_15min import FEATURE_COLS_15MIN_MT, ensure_strategy_onehots
from feature_compile_heating_dsm import (
    HP_ON_COLS,
    OCC_FRAC_COLS,
    STRATEGY_IDS,
    TARGET_COLS,
    ZONE_TEMP_COLS,
)
from hybrid_sanity import annotate_walk_sanity

STEPS = 96
CONTRACT_VERSION = "hybrid_dsm_96_v1"
HONESTY = "HYBRID_SCREENING"
CONTROL_CONTRACT_VERSION = "control_strategies_v1"
_CONTROL_DIR = Path(__file__).resolve().parents[1] / "contracts" / CONTROL_CONTRACT_VERSION


def load_strategy_control(strategy_id: str) -> dict[str, Any]:
    """Load farm-SoT 96-step control fixture (desktop strategies only — no PRBS)."""
    if strategy_id.startswith("prbs"):
        raise ValueError("PRBS not offered on desktop; use farm-only PRBS arms")
    path = _CONTROL_DIR / f"{strategy_id}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing control contract {path} — run scripts/export_control_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def schedule_from_strategy_fixture(strategy_id: str) -> dict[str, Any]:
    """Build hybrid_rollout control_96 dict from versioned fixture."""
    doc = load_strategy_control(strategy_id)
    steps = doc["steps"]
    out: dict[str, Any] = {"strategy_id": strategy_id}
    for c in OCC_FRAC_COLS + HP_ON_COLS:
        out[c] = [float(steps[i][c]) for i in range(STEPS)]
    for k in ("preheat_lead_h", "stagger_min", "unocc_htg_sp_f", "occ_htg_sp_f"):
        out[k] = float(steps[0][k])
    return out


@dataclass
class HybridModels:
    baseline: Any  # predict → (1, 7)
    delta: Any
    feature_cols: list[str]


def load_onnx_model(path: Path) -> Any:
    """ONNX session wrapper with sklearn-like ``predict`` → (1, 7)."""
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    class _Onnx7:
        def predict(self, x: np.ndarray) -> np.ndarray:
            x = np.asarray(x, dtype=np.float32)
            if x.ndim == 1:
                x = x.reshape(1, -1)
            out = sess.run(None, {in_name: x})[0]
            return np.asarray(out, dtype=float)

    return _Onnx7()


def load_hybrid_onnx(
    baseline_onnx: Path,
    delta_onnx: Path,
    feature_meta: Path | None = None,
) -> HybridModels:
    """Load the same ONNX pair the Rust desktop uses."""
    if baseline_onnx is None or delta_onnx is None:
        raise FileNotFoundError(
            "baseline_onnx and delta_onnx are required "
            "(got None — check artifact paths / _find helper)"
        )
    baseline_onnx = Path(baseline_onnx)
    delta_onnx = Path(delta_onnx)
    if not baseline_onnx.is_file():
        raise FileNotFoundError(baseline_onnx)
    if not delta_onnx.is_file():
        raise FileNotFoundError(delta_onnx)
    cols = list(FEATURE_COLS_15MIN_MT)
    meta_path = feature_meta
    if meta_path is None:
        cand = baseline_onnx.with_name(baseline_onnx.name.replace(".onnx", "_feature_meta.json"))
        if cand.is_file():
            meta_path = cand
    if meta_path is not None and Path(meta_path).is_file():
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        cols = list(meta.get("feature_cols") or cols)
    return HybridModels(
        baseline=load_onnx_model(baseline_onnx),
        delta=load_onnx_model(delta_onnx),
        feature_cols=cols,
    )


def load_joblib_model(path: Path) -> tuple[Any, list[str], list[str]]:
    import joblib

    blob = joblib.load(path)
    return blob["model"], list(blob["feature_cols"]), list(blob["target_cols"])


def _finite(val: Any, fallback: float) -> float:
    """Coerce to float; replace NaN/inf/None with fallback (NaN is truthy in Python)."""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return float(fallback)
    return x if np.isfinite(x) else float(fallback)


def _row_features(row: dict[str, float], feature_cols: list[str]) -> np.ndarray:
    """Fail closed: every required feature must be present and finite."""
    missing = [c for c in feature_cols if c not in row]
    if missing:
        raise ValueError(f"missing required feature(s): {missing[:8]}")
    x = np.empty(len(feature_cols), dtype=float)
    for i, c in enumerate(feature_cols):
        try:
            v = float(row[c])
        except (TypeError, ValueError) as e:
            raise ValueError(f"non-finite/required feature {c}") from e
        if not np.isfinite(v):
            raise ValueError(f"non-finite required feature {c}")
        x[i] = v
    return x


def _require_weather_series(weather: dict[str, Any], key: str) -> list[float]:
    if key not in weather or weather[key] is None:
        raise ValueError(f"weather_forecast_96 missing required finite series {key}")
    series = weather[key]
    if not isinstance(series, (list, tuple, np.ndarray)) or len(series) < STEPS:
        raise ValueError(f"weather_forecast_96.{key} must have length >= {STEPS}")
    out: list[float] = []
    for i, v in enumerate(series[:STEPS]):
        try:
            x = float(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"weather_forecast_96.{key}[{i}] not finite") from e
        if not np.isfinite(x):
            raise ValueError(f"weather_forecast_96.{key}[{i}] not finite")
        out.append(x)
    return out


def _predict7(model: Any, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float).reshape(-1)
    if not np.isfinite(x).all():
        raise ValueError("feature vector has non-finite values")
    y = np.asarray(model.predict(x.reshape(1, -1)), dtype=float).reshape(-1)
    if y.size < 7:
        raise ValueError(f"expected 7 outputs, got {y.size}")
    return y[:7]


def init_state_from_contract(init: dict[str, Any]) -> dict[str, float]:
    """Lag init = measured midnight state from JSON — never hardcode 80/35."""
    required = ["facility_kw", "oat_f", *ZONE_TEMP_COLS]
    for k in required:
        if k not in init or init[k] is None or not np.isfinite(float(init[k])):
            raise ValueError(f"init missing finite {k} (measured midnight required)")
    kw = float(init["facility_kw"])
    state = {
        "facility_kw_lag1": kw,
        "facility_kw_lag2": _finite(init.get("facility_kw_lag2"), kw),
        "oat_lag1": float(init["oat_f"]),
    }
    for c in ZONE_TEMP_COLS:
        state[f"{c}_lag1"] = float(init[c])
    return state


def _calendar_features(step: int, meta: dict[str, Any]) -> dict[str, float]:
    from interval15 import calendar_features_for_step

    occupied = float(meta.get("occupied_schedule", [0.0] * 96)[step])
    cal = calendar_features_for_step(step)
    return {
        **cal,
        "month": float(meta.get("month", 1)),
        "doy": float(meta.get("doy", 1)),
        "is_weekend": float(meta.get("is_weekend", 0)),
        "occupied": occupied,
    }


def _control_at(schedule: dict[str, list[float]], step: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for c in OCC_FRAC_COLS + HP_ON_COLS:
        series = schedule.get(c, [1.0] * 96)
        out[c] = float(series[step] if step < len(series) else series[-1])
    out["sum_occ_frac"] = float(sum(out[c] for c in OCC_FRAC_COLS))
    out["sum_hp_on"] = float(sum(out[c] for c in HP_ON_COLS))
    for k in ("preheat_lead_h", "stagger_min", "unocc_htg_sp_f", "occ_htg_sp_f"):
        series = schedule.get(k)
        if series is None:
            out[k] = {"preheat_lead_h": 0.0, "stagger_min": 0.0, "unocc_htg_sp_f": 64.0, "occ_htg_sp_f": 68.0}[k]
        else:
            out[k] = float(series[step] if isinstance(series, list) else series)
    sid = schedule.get("strategy_id", "baseline")
    if isinstance(sid, list):
        sid = sid[step] if step < len(sid) else sid[-1]
    for s in STRATEGY_IDS:
        out[f"strategy_{s}"] = 1.0 if s == sid else 0.0
    return out


def build_row(
    *,
    step: int,
    weather: dict[str, Any],
    schedule: dict[str, Any],
    state: dict[str, float],
    meta: dict[str, Any],
    hdd_acc: float,
) -> tuple[dict[str, float], float]:
    """Build one feature row at step t using weather[t] only (no future leak).

    Returns (row, updated_hdd_acc). ``hdd_acc`` is caller-owned local state —
    never written onto the contract dict.
    """
    if step < 0 or step >= STEPS:
        raise ValueError(f"step must be in [0, {STEPS}), got {step}")
    # Fail closed: oat/rh/ghi required — never invent RH=50 or GHI=0.
    oat_s = _require_weather_series(weather, "oat_f")
    rh_s = _require_weather_series(weather, "rh_pct")
    ghi_s = _require_weather_series(weather, "ghi")
    oat = float(oat_s[step])
    rh = float(rh_s[step])
    ghi = float(ghi_s[step])
    hdd = max(0.0, 65.0 - oat)
    hdd_acc_next = hdd_acc + (hdd if step < 28 else 0.0)
    cal = _calendar_features(step, meta)
    wx = {
        "oat_f": oat,
        "oat_lag1": float(state["oat_lag1"]),
        "rh_pct": rh,
        "ghi": ghi,
        "hdd65": hdd,
        "hdd65_cum_night": hdd_acc_next,
    }
    row = {**cal, **wx, **_control_at(schedule, step), **state}
    return row, hdd_acc_next


def rollout_96(
    models: HybridModels,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Run 96-step hybrid simulator from versioned JSON contract."""
    if contract.get("contract_version") not in (CONTRACT_VERSION, "hybrid_dsm_96_v1"):
        raise ValueError(f"unsupported contract_version={contract.get('contract_version')}")
    init = contract["init"]
    weather = contract["weather_forecast_96"]
    baseline_ctrl = contract["baseline_control_96"]
    dsm_ctrl = contract["dsm_control_96"]
    meta = contract.get("calendar", {})
    comfort_sp = float(contract.get("comfort_htg_sp_f", 68.0))
    comfort_band = float(contract.get("comfort_band_f", 2.0))

    state_b = init_state_from_contract(init)
    state_d = dict(state_b)  # delta lags start at 0 intervention
    for c in ZONE_TEMP_COLS:
        state_d[f"{c}_lag1"] = 0.0
    state_d["facility_kw_lag1"] = 0.0
    state_d["facility_kw_lag2"] = 0.0

    steps_out = []
    cum_kwh_b = cum_kwh_d = 0.0
    peak_b = peak_d = -1e9
    peak_b_t = peak_d_t = 0
    viol = 0
    hdd_acc = 0.0  # local night-HDD accumulator (never mutate the contract)

    for step in range(STEPS):
        # Shared weather[t] / night HDD for both arms; controls+lags differ.
        row_b, hdd_acc = build_row(
            step=step,
            weather=weather,
            schedule=baseline_ctrl,
            state=state_b,
            meta=meta,
            hdd_acc=hdd_acc,
        )
        cal = _calendar_features(step, meta)
        wx = {
            "oat_f": row_b["oat_f"],
            "oat_lag1": state_d["oat_lag1"],
            "rh_pct": row_b["rh_pct"],
            "ghi": row_b["ghi"],
            "hdd65": row_b["hdd65"],
            "hdd65_cum_night": hdd_acc,
        }
        row_d_ctrl = {**cal, **wx, **_control_at(dsm_ctrl, step), **state_d}

        xb = _row_features(row_b, models.feature_cols)
        xd = _row_features(row_d_ctrl, models.feature_cols)
        base_y = _predict7(models.baseline, xb)
        delta_y = _predict7(models.delta, xd)
        hybrid_y = base_y + delta_y

        kw_b, kw_h = float(base_y[0]), float(hybrid_y[0])
        oat = float(row_b["oat_f"])
        cum_kwh_b += kw_b * 0.25
        cum_kwh_d += kw_h * 0.25
        if kw_b > peak_b:
            peak_b, peak_b_t = kw_b, step
        if kw_h > peak_d:
            peak_d, peak_d_t = kw_h, step

        temps = {ZONE_TEMP_COLS[i]: float(hybrid_y[1 + i]) for i in range(6)}
        for t in temps.values():
            if t < comfort_sp - comfort_band:
                viol += 1

        steps_out.append(
            {
                "step_15": step,
                "baseline_facility_kw": kw_b,
                "delta_facility_kw": float(delta_y[0]),
                "hybrid_facility_kw": kw_h,
                "baseline_zone_temps_f": {ZONE_TEMP_COLS[i]: float(base_y[1 + i]) for i in range(6)},
                "delta_zone_temps_f": {ZONE_TEMP_COLS[i]: float(delta_y[1 + i]) for i in range(6)},
                "hybrid_zone_temps_f": temps,
                "cumulative_kwh_baseline": cum_kwh_b,
                "cumulative_kwh_hybrid": cum_kwh_d,
                "running_peak_kw_baseline": peak_b,
                "running_peak_kw_hybrid": peak_d,
                "running_peak_step_baseline": peak_b_t,
                "running_peak_step_hybrid": peak_d_t,
                "comfort_sp_f": comfort_sp,
                "comfort_violations_cum": viol,
            }
        )

        # update lags
        state_b["facility_kw_lag2"] = state_b["facility_kw_lag1"]
        state_b["facility_kw_lag1"] = kw_b
        state_b["oat_lag1"] = oat
        for i, c in enumerate(ZONE_TEMP_COLS):
            state_b[f"{c}_lag1"] = float(base_y[1 + i])

        state_d["facility_kw_lag2"] = state_d["facility_kw_lag1"]
        state_d["facility_kw_lag1"] = float(delta_y[0])
        state_d["oat_lag1"] = oat
        for i, c in enumerate(ZONE_TEMP_COLS):
            state_d[f"{c}_lag1"] = float(delta_y[1 + i])

    walk = {
        "contract_version": CONTRACT_VERSION,
        "honesty": HONESTY,
        "steps": steps_out,
        "summary": {
            "cumulative_kwh_baseline": cum_kwh_b,
            "cumulative_kwh_hybrid": cum_kwh_d,
            "peak_kw_baseline": peak_b,
            "peak_kw_hybrid": peak_d,
            "peak_step_baseline": peak_b_t,
            "peak_step_hybrid": peak_d_t,
            "comfort_violations": viol,
            "delta_peak_kw": peak_d - peak_b,
            "delta_kwh": cum_kwh_d - cum_kwh_b,
        },
    }
    return annotate_walk_sanity(walk)


def make_fixture_contract(*, seed: int = 21, dsm_strategy: str = "stagger_preheat") -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    oat = 20.0 + 10.0 * np.sin(np.linspace(0, 2 * np.pi, 96)) + rng.normal(0, 1, 96)
    init = {
        "facility_kw": 12.0,
        "facility_kw_lag2": 12.0,
        "oat_f": float(oat[0]),
        **{c: 68.0 for c in ZONE_TEMP_COLS},
    }
    occ = [1.0 if 28 <= i < 64 else 0.0 for i in range(96)]
    baseline_control = schedule_from_strategy_fixture("baseline")
    dsm_control = schedule_from_strategy_fixture(dsm_strategy)
    return {
        "contract_version": CONTRACT_VERSION,
        "honesty": HONESTY,
        "control_contract_version": CONTROL_CONTRACT_VERSION,
        "interval_semantics": {
            "timestamp": "quarter_hour_interval_end_hour_ending",
            "init": "measured_midnight_state_only",
            "predictions": "96 steps covering 00:15 through 24:00",
        },
        "init": init,
        "calendar": {
            "month": 1,
            "doy": 15,
            "is_weekend": 0.0,
            "occupied_schedule": occ,
        },
        "weather_forecast_96": {
            "oat_f": oat.tolist(),
            "rh_pct": (50 + rng.normal(0, 5, 96)).tolist(),
            "ghi": np.clip(800 * np.sin(np.linspace(-0.2, 3.2, 96)), 0, None).tolist(),
            "weather_mode": "synthetic_fixture",
        },
        "baseline_control_96": baseline_control,
        "dsm_control_96": dsm_control,
        "comfort_htg_sp_f": 68.0,
        "comfort_band_f": 2.0,
    }
