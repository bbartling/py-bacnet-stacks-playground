"""Overlap-window calibration: AMY EPW + custom RunPeriod + scorecard vs vibe19 seed.

Usage:
  python calibrate.py --bundle <vibe19_export_dir> [--seed model_seed.json] [--dry-run]
  python calibrate.py --bundle <dir> --validation-months 3
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.config import (
    ARTIFACTS,
    DEFAULT_PROTOTYPE_IDF,
    ROOT,
    STATUS_CALIBRATED_NOT_VALIDATED,
    STATUS_CONCEPTUAL_ONLY,
    STATUS_FAILED_VALIDATION,
    STATUS_VALIDATED,
    SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
    weather_suitability,
)
from wattlab.energyplus.mcp import simulate
from wattlab.energyplus.patches import apply_hourly_outputs, apply_run_period
from wattlab.energyplus.patches.schedules import apply_fan_avail_continuous
from wattlab.energyplus.results import annual_from_output_dir, file_sha256
from wattlab.energyplus.manifest import build_run_manifest, write_run_manifest
from wattlab.defaults import resolve_profile
from wattlab.weather.epw import build_amy_epw

# ASHRAE Guideline 14 monthly thresholds
NMBE_PASS = 5.0
CVRMSE_PASS = 15.0


def scale_monthly_energy(
    monthly: list[dict[str, Any]],
    *,
    area_scale: float | None,
) -> list[dict[str, Any]]:
    """Scale prototype monthly kWh/therms toward site for G14 absolute compare."""
    if not area_scale or area_scale <= 0:
        return list(monthly or [])
    out: list[dict[str, Any]] = []
    for row in monthly or []:
        r = dict(row)
        if r.get("electricity_kwh") is not None:
            r["electricity_kwh_unscaled"] = r["electricity_kwh"]
            r["electricity_kwh"] = round(float(r["electricity_kwh"]) * area_scale, 2)
        if r.get("natural_gas_therm") is not None:
            r["natural_gas_therm_unscaled"] = r["natural_gas_therm"]
            r["natural_gas_therm"] = round(float(r["natural_gas_therm"]) * area_scale, 2)
        out.append(r)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nmbe_cvrmse(observed: list[float], simulated: list[float]) -> dict[str, float]:
    """NMBE and CVRMSE in percent (ASHRAE Guideline 14)."""
    pairs = [(float(o), float(s)) for o, s in zip(observed, simulated) if o is not None and s is not None]
    pairs = [(o, s) for o, s in pairs if not (math.isnan(o) or math.isnan(s))]
    if not pairs:
        return {"n": 0, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": float("nan")}
    n = len(pairs)
    mean_obs = sum(o for o, _ in pairs) / n
    if abs(mean_obs) < 1e-12:
        return {"n": n, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": mean_obs}
    nmbe = sum(o - s for o, s in pairs) / (n * mean_obs) * 100.0
    # Guideline 14 uses (n - 1) for CVRMSE when n > 1
    denom = n - 1 if n > 1 else n
    mse = sum((o - s) ** 2 for o, s in pairs) / denom
    cvrmse = math.sqrt(mse) / abs(mean_obs) * 100.0
    return {
        "n": n,
        "nmbe_pct": round(nmbe, 3),
        "cvrmse_pct": round(cvrmse, 3),
        "mean_obs": round(mean_obs, 3),
    }


def _pass_fail(stats: dict[str, float]) -> str:
    if stats.get("n", 0) == 0 or math.isnan(stats.get("nmbe_pct", float("nan"))):
        return "insufficient_data"
    if abs(stats["nmbe_pct"]) <= NMBE_PASS and stats["cvrmse_pct"] <= CVRMSE_PASS:
        return "pass"
    return "fail"


def pearson_corr(a: list[float], b: list[float]) -> float:
    """Pearson correlation; nan if undefined."""
    n = min(len(a), len(b))
    if n < 3:
        return float("nan")
    xs = a[:n]
    ys = b[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x < 1e-12 or den_y < 1e-12:
        return float("nan")
    return num / (den_x * den_y)


def detect_hour_shift(
    observed: list[float],
    simulated: list[float],
    *,
    max_lag: int = 3,
) -> dict[str, Any]:
    """Lag-scan correlation to flag likely hour-ending / alignment errors.

    Does **not** auto-correct — reports best lag and whether a non-zero shift
    improves correlation vs lag 0. Warning only.
    """
    n = min(len(observed), len(simulated))
    if n < max(12, 2 * max_lag + 3):
        return {
            "best_lag_hours": 0,
            "corr_at_0": float("nan"),
            "best_corr": float("nan"),
            "warning": None,
            "note": "insufficient_samples",
        }
    obs = [float(x) for x in observed[:n]]
    sim = [float(x) for x in simulated[:n]]
    corr0 = pearson_corr(obs, sim)
    best_lag = 0
    best_corr = corr0 if not math.isnan(corr0) else -2.0
    per_lag: list[dict[str, Any]] = [{"lag": 0, "corr": None if math.isnan(corr0) else round(corr0, 4)}]

    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            continue
        if lag > 0:
            # simulated leads observed by ``lag`` hours → shift sim later
            o = obs[lag:]
            s = sim[: n - lag]
        else:
            o = obs[: n + lag]
            s = sim[-lag:]
        c = pearson_corr(o, s)
        per_lag.append({"lag": lag, "corr": None if math.isnan(c) else round(c, 4)})
        score = c if not math.isnan(c) else -2.0
        if score > best_corr:
            best_corr = score
            best_lag = lag

    warning = None
    if best_lag != 0 and not math.isnan(corr0) and best_corr > corr0 + 0.02:
        warning = (
            f"Possible {best_lag}-hour timestamp shift "
            f"(corr@{best_lag}={best_corr:.3f} vs corr@0={corr0:.3f}). "
            "Check hour-ending vs hour-beginning and timezone/DST."
        )
    return {
        "best_lag_hours": best_lag,
        "corr_at_0": None if math.isnan(corr0) else round(corr0, 4),
        "best_corr": round(best_corr, 4) if best_corr > -1.5 else None,
        "per_lag": per_lag,
        "warning": warning,
        "note": "warning_only_no_auto_correct",
    }


def aggregate_signatures(rows: list[dict[str, str]], kind: str = "fan") -> dict[int, float]:
    """Mean on_fraction by OAT bin_start for a signature kind."""
    buckets: dict[int, list[float]] = {}
    for r in rows:
        if (r.get("kind") or "").strip() != kind:
            continue
        try:
            b = int(float(r["bin_start"]))
            frac = float(r["on_fraction"])
        except (KeyError, TypeError, ValueError):
            continue
        buckets.setdefault(b, []).append(frac)
    return {b: sum(v) / len(v) for b, v in buckets.items()}


def parse_eplusout_hourly(sim_dir: Path) -> list[dict[str, Any]]:
    """Parse eplusout.csv hourly rows into {oat_c, fan_w, cool_w, ...}."""
    path = sim_dir / "eplusout.csv"
    if not path.is_file():
        alts = list(sim_dir.glob("eplusout*.csv"))
        if not alts:
            return []
        path = alts[0]
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []
        header_l = [h.strip().lower() for h in header]

        def find(*needles: str) -> int | None:
            for i, h in enumerate(header_l):
                if all(n in h for n in needles):
                    return i
            return None

        i_oat = find("outdoor", "drybulb") or find("site outdoor air drybulb")
        i_fan = find("fan electricity rate")
        i_cool = find("cooling coil total cooling rate") or find("chiller electricity rate")
        i_elec = None
        for i, h in enumerate(header_l):
            if "electricity:facility" in h and "hourly" in h:
                i_elec = i
                break
            if i_elec is None and "electricity:facility" in h:
                i_elec = i

        for raw in reader:
            if not raw or len(raw) < 2:
                continue

            def _f(idx: int | None) -> float:
                if idx is None or idx >= len(raw):
                    return float("nan")
                try:
                    return float(raw[idx])
                except ValueError:
                    return float("nan")

            rows.append(
                {
                    "oat_c": _f(i_oat),
                    "fan_w": _f(i_fan),
                    "cool_w": _f(i_cool),
                    "elec_j": _f(i_elec),
                }
            )
    return rows


def simulated_signatures_from_hourly(
    hourly: list[dict[str, Any]],
    *,
    bin_width_f: float = 5.0,
) -> dict[str, dict[int, float]]:
    """Build fan / mech_cooling on_fraction by OAT bin from hourly sim rows."""
    fan_buckets: dict[int, list[int]] = {}
    cool_buckets: dict[int, list[int]] = {}
    for r in hourly:
        oat_c = r.get("oat_c")
        if oat_c is None or math.isnan(oat_c):
            continue
        oat_f = oat_c * 9.0 / 5.0 + 32.0
        if oat_f < 40 or oat_f > 110:
            continue
        b = int(math.floor(oat_f / bin_width_f) * bin_width_f)
        fan_on = 1 if (r.get("fan_w") or 0) > 10.0 else 0
        cool_on = 1 if (r.get("cool_w") or 0) > 100.0 else 0
        fan_buckets.setdefault(b, []).append(fan_on)
        cool_buckets.setdefault(b, []).append(cool_on)

    def _frac(buckets: dict[int, list[int]]) -> dict[int, float]:
        return {b: sum(v) / len(v) for b, v in buckets.items() if v}

    return {"fan": _frac(fan_buckets), "mech_cooling": _frac(cool_buckets)}


def compare_signature_maps(
    observed: dict[int, float],
    simulated: dict[int, float],
) -> dict[str, Any]:
    bins = sorted(set(observed) & set(simulated))
    if not bins:
        return {
            "bins_compared": 0,
            "stats": nmbe_cvrmse([], []),
            "pass_fail": "insufficient_data",
            "per_bin": [],
        }
    obs = [observed[b] for b in bins]
    sim = [simulated[b] for b in bins]
    stats = nmbe_cvrmse(obs, sim)
    per_bin = [
        {
            "bin_start": b,
            "observed_on_fraction": round(observed[b], 4),
            "simulated_on_fraction": round(simulated[b], 4),
            "delta": round(simulated[b] - observed[b], 4),
        }
        for b in bins
    ]
    return {
        "bins_compared": len(bins),
        "stats": stats,
        "pass_fail": _pass_fail(stats),
        "per_bin": per_bin,
    }


def normalize_bill_month_key(value: Any, *, default_year: int | None = None) -> str | None:
    """Normalize bill/sim month keys to ``YYYY-MM`` when possible.

    Accepts:
    - ``YYYY-MM`` / ``YYYY-MM-DD`` strings
    - integer month 1–12 (legacy) → ``{default_year}-{mm}`` when year known
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 7 and s[4] == "-":
            return s[:7]
        try:
            m = int(float(s))
        except (TypeError, ValueError):
            return None
    else:
        try:
            m = int(value)
        except (TypeError, ValueError):
            return None
    if not 1 <= m <= 12:
        return None
    if default_year is None:
        # Legacy bare month: keep as zero-padded sentinel year 0001 so same-month
        # joins still work within a single synthetic year, but period overlap
        # detection can see the missing calendar year.
        return f"0001-{m:02d}"
    return f"{int(default_year)}-{m:02d}"


def _bill_calendar_years(bills: list[dict[str, Any]]) -> set[int]:
    years: set[int] = set()
    for b in bills:
        key = normalize_bill_month_key(b.get("month") or b.get("period"))
        if key and not key.startswith("0001-"):
            years.add(int(key[:4]))
    return years


def load_utility_bills(bundle: Path, seed: dict[str, Any]) -> list[dict[str, Any]]:
    bills = seed.get("utility_bills")
    if isinstance(bills, list) and bills:
        out: list[dict[str, Any]] = []
        for b in bills:
            if not isinstance(b, dict):
                continue
            key = normalize_bill_month_key(b.get("month") or b.get("period"))
            if key is None:
                continue
            row = dict(b)
            row["month"] = key
            row["period"] = key
            out.append(row)
        return out
    path = bundle / "utility_bills.csv"
    rows = _read_csv(path)
    out = []
    for r in rows:
        try:
            key = normalize_bill_month_key(r.get("month") or r.get("period"))
            if key is None:
                continue
            out.append(
                {
                    "month": key,
                    "period": key,
                    "kwh": float(r["kwh"]) if r.get("kwh") not in (None, "") else None,
                    "therms": float(r["therms"]) if r.get("therms") not in (None, "") else None,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def month_keys_for_data_window(data_window: dict[str, Any] | None) -> list[str]:
    """Inclusive ``YYYY-MM`` keys from ``data_window`` start→end."""
    if not data_window:
        return []
    start_raw = (
        data_window.get("start_utc")
        or data_window.get("start")
        or data_window.get("start_date")
    )
    end_raw = (
        data_window.get("end_utc")
        or data_window.get("end")
        or data_window.get("end_date")
    )
    if not isinstance(start_raw, str) or not isinstance(end_raw, str):
        return []
    if len(start_raw) < 7 or len(end_raw) < 7:
        return []
    try:
        y0, m0 = int(start_raw[:4]), int(start_raw[5:7])
        y1, m1 = int(end_raw[:4]), int(end_raw[5:7])
    except (TypeError, ValueError):
        return []
    if not (1 <= m0 <= 12 and 1 <= m1 <= 12):
        return []
    keys: list[str] = []
    y, m = y0, m0
    # Cap at 36 months to avoid runaway loops on bad windows.
    for _ in range(36):
        keys.append(f"{y:04d}-{m:02d}")
        if (y, m) >= (y1, m1):
            break
        m += 1
        if m > 12:
            m = 1
            y += 1
    return keys


def calendar_month_key_map(
    window_keys: list[str],
) -> tuple[dict[int, str], str | None]:
    """Map calendar month 1–12 → unique ``YYYY-MM`` in the window.

    Returns an empty map + reason when the same calendar month appears twice
    (RunPeriod longer than 12 months) — refuse silent wrong joins.
    """
    by_m: dict[int, str] = {}
    for key in window_keys:
        if len(key) < 7 or key[4] != "-":
            continue
        try:
            month_num = int(key[5:7])
        except ValueError:
            continue
        if not 1 <= month_num <= 12:
            continue
        if month_num in by_m:
            return (
                {},
                "data_window spans duplicate calendar months "
                f"({by_m[month_num]} and {key}); refuse bare-month join",
            )
        by_m[month_num] = key
    return by_m, None


def compare_bills_to_monthly(
    bills: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    *,
    data_window: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dual-fuel monthly G14 compare (electricity kWh + gas therms when present).

    Keys months as ``YYYY-MM`` when available. Bare E+ months (1–12) are stamped
    from the full ``data_window`` span (multi-year aware). When bill years and
    simulation / telemetry windows do not overlap, returns ``period_mismatch``
    and does not report a false G14 pass on coincidental month numbers.
    """
    window_keys = month_keys_for_data_window(data_window)
    cal_map, cal_dup_reason = calendar_month_key_map(window_keys)

    sim_year: int | None = None
    if window_keys:
        sim_year = int(window_keys[0][:4])
    elif data_window:
        for k in ("start_utc", "end_utc", "start", "end"):
            v = data_window.get(k)
            if isinstance(v, str) and len(v) >= 4 and v[:4].isdigit():
                sim_year = int(v[:4])
                break

    bill_years = _bill_calendar_years(bills)
    # Infer sim year from monthly rows when present as YYYY-MM.
    for m in monthly:
        key = normalize_bill_month_key(m.get("month") or m.get("period"))
        if key and not key.startswith("0001-"):
            sim_year = int(key[:4])
            break

    period_mismatch = False
    mismatch_reason = ""
    if cal_dup_reason:
        period_mismatch = True
        mismatch_reason = cal_dup_reason
    elif bill_years and window_keys:
        bill_keys = {
            normalize_bill_month_key(b.get("month") or b.get("period"))
            for b in bills
        }
        bill_keys.discard(None)
        if bill_keys and not (bill_keys & set(window_keys)):
            period_mismatch = True
            mismatch_reason = (
                f"bill months do not overlap data_window "
                f"{window_keys[0]}…{window_keys[-1]}"
            )
    elif bill_years and sim_year is not None and sim_year not in bill_years:
        # Also accept adjacent-year windows that still share YYYY-MM keys below.
        period_mismatch = True
        mismatch_reason = (
            f"bill_years={sorted(bill_years)} do not include simulation/telemetry "
            f"year={sim_year}; refuse month-number-only join"
        )

    by_m: dict[str, dict[str, Any]] = {}
    for m in monthly:
        raw = m.get("month") or m.get("period")
        key = normalize_bill_month_key(raw)
        if key and not key.startswith("0001-"):
            by_m[key] = m
            continue
        # Bare month 1–12: map via multi-year window when available.
        month_num: int | None = None
        if key and key.startswith("0001-"):
            month_num = int(key[5:7])
        elif isinstance(raw, (int, float)) or (
            isinstance(raw, str) and raw.strip().isdigit()
        ):
            try:
                month_num = int(float(raw))
            except (TypeError, ValueError):
                month_num = None
        if month_num is not None and cal_map and month_num in cal_map:
            by_m[cal_map[month_num]] = m
        elif month_num is not None and sim_year is not None and not cal_map:
            by_m[f"{sim_year}-{month_num:02d}"] = m
        elif key:
            by_m[key] = m

    obs_kwh: list[float] = []
    sim_kwh: list[float] = []
    obs_therms: list[float] = []
    sim_therms: list[float] = []
    per_month: list[dict[str, Any]] = []
    unmatched_bills = 0
    for b in bills:
        key = normalize_bill_month_key(b.get("month") or b.get("period"), default_year=sim_year)
        if key is None:
            continue
        # If bills are real YYYY-MM and sim is legacy 0001-MM, try month-only
        # only when years are unknown/compatible — never across mismatched years.
        row = by_m.get(key)
        if row is None and key.startswith("0001-") is False and sim_year is None and not cal_map:
            # Sim months are bare 1–12 → 0001-MM
            row = by_m.get(f"0001-{key[5:]}")
        if row is None and key.startswith("0001-"):
            # Prefer exact year match from bills when sim is bare-month.
            for y in sorted(bill_years):
                cand = f"{y}-{key[5:]}"
                if cand in by_m:
                    row = by_m[cand]
                    key = cand
                    break
        if row is None:
            unmatched_bills += 1
            continue
        if period_mismatch and not key.startswith("0001-"):
            # Do not accumulate metrics across non-overlapping calendar years.
            continue
        entry: dict[str, Any] = {"month": key, "period": key}
        o_kwh = b.get("kwh")
        s_kwh = row.get("electricity_kwh")
        if o_kwh is not None and s_kwh is not None:
            obs_kwh.append(float(o_kwh))
            sim_kwh.append(float(s_kwh))
            entry["observed_kwh"] = float(o_kwh)
            entry["simulated_kwh"] = float(s_kwh)
            entry["delta_kwh"] = float(s_kwh) - float(o_kwh)
        o_th = b.get("therms")
        s_th = row.get("natural_gas_therm")
        if o_th is not None and s_th is not None:
            obs_therms.append(float(o_th))
            sim_therms.append(float(s_th))
            entry["observed_therms"] = float(o_th)
            entry["simulated_therms"] = float(s_th)
            entry["delta_therms"] = float(s_th) - float(o_th)
        if len(entry) > 2:
            per_month.append(entry)

    # Recompute period_mismatch if no overlapping YYYY-MM keys joined.
    if bill_years and per_month == [] and unmatched_bills:
        period_mismatch = True
        if not mismatch_reason:
            mismatch_reason = "no overlapping YYYY-MM periods between bills and simulation"

    elec_stats = nmbe_cvrmse(obs_kwh, sim_kwh)
    gas_stats = nmbe_cvrmse(obs_therms, sim_therms)
    elec_pf = _pass_fail(elec_stats)
    gas_pf = _pass_fail(gas_stats)

    fuels_compared: list[str] = []
    fuel_results: list[str] = []
    if elec_stats.get("n", 0) > 0:
        fuels_compared.append("electricity")
        fuel_results.append(elec_pf)
    if gas_stats.get("n", 0) > 0:
        fuels_compared.append("natural_gas")
        fuel_results.append(gas_pf)

    if period_mismatch:
        overall = "period_mismatch"
        elec_pf = "period_mismatch" if elec_stats.get("n", 0) == 0 else elec_pf
        gas_pf = "period_mismatch" if gas_stats.get("n", 0) == 0 else gas_pf
    elif not fuel_results:
        overall = "insufficient_data"
    elif any(p == "fail" for p in fuel_results):
        overall = "fail"
    elif any(p == "insufficient_data" for p in fuel_results):
        overall = "insufficient_data"
    elif all(p == "pass" for p in fuel_results):
        overall = "pass"
    else:
        overall = "fail"

    return {
        "months_compared": len(per_month),
        "fuels_compared": fuels_compared,
        "stats": elec_stats,
        "stats_electricity": elec_stats,
        "stats_natural_gas": gas_stats,
        "pass_fail_electricity": elec_pf,
        "pass_fail_natural_gas": gas_pf,
        "pass_fail": overall,
        "period_mismatch": period_mismatch,
        "period_mismatch_reason": mismatch_reason,
        "bill_years": sorted(bill_years),
        "simulation_year": sim_year,
        "simulation_months": window_keys or None,
        "per_month": per_month,
        "thresholds": {"nmbe_pct": NMBE_PASS, "cvrmse_pct": CVRMSE_PASS},
    }


def split_bills_for_holdout(
    bills: list[dict[str, Any]],
    *,
    validation_months: int = 0,
    validation_start: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Split monthly bills into calibration vs validation sets.

    Default: hold out the last ``validation_months`` contiguous months (by month number
    order as present in ``bills``). Optional ``validation_start`` (1–12) starts the
    holdout at that calendar month when present.
    """
    def _month_sort_key(b: dict[str, Any]) -> tuple[int, int]:
        key = normalize_bill_month_key(b.get("month") or b.get("period"))
        if key is None:
            return (0, 0)
        try:
            return (int(key[:4]), int(key[5:7]))
        except ValueError:
            return (0, 0)

    def _month_num(b: dict[str, Any]) -> int:
        key = normalize_bill_month_key(b.get("month") or b.get("period"))
        if key is None:
            return 0
        try:
            return int(key[5:7])
        except ValueError:
            try:
                return int(b["month"])
            except (TypeError, ValueError):
                return 0

    meta: dict[str, Any] = {
        "validation_months_requested": validation_months,
        "validation_start": validation_start,
        "min_months_for_holdout": 6,
    }
    ordered = sorted(
        [b for b in bills if b.get("month") or b.get("period")],
        key=_month_sort_key,
    )
    if validation_months <= 0 or len(ordered) < 6:
        meta["applied"] = False
        meta["reason"] = (
            "holdout_disabled"
            if validation_months <= 0
            else f"need_at_least_6_months_have_{len(ordered)}"
        )
        return ordered, [], meta

    n_val = min(validation_months, len(ordered) - 3)  # keep >=3 cal months
    if n_val <= 0:
        meta["applied"] = False
        meta["reason"] = "not_enough_months_after_reserve"
        return ordered, [], meta

    if validation_start is not None:
        months = [_month_num(b) for b in ordered]
        if validation_start not in months:
            meta["applied"] = False
            meta["reason"] = f"validation_start_{validation_start}_not_in_bills"
            return ordered, [], meta
        val_set: set[int] = set()
        m = int(validation_start)
        for _ in range(n_val):
            val_set.add(m)
            m = 1 if m == 12 else m + 1
        cal = [b for b in ordered if _month_num(b) not in val_set]
        val = [b for b in ordered if _month_num(b) in val_set]
    else:
        cal = ordered[:-n_val]
        val = ordered[-n_val:]

    meta["applied"] = True
    meta["calibration_months"] = [
        normalize_bill_month_key(b.get("month") or b.get("period")) or b.get("month") for b in cal
    ]
    meta["validation_months"] = [
        normalize_bill_month_key(b.get("month") or b.get("period")) or b.get("month") for b in val
    ]
    meta["note"] = (
        "Signature shape comparison stays whole-window "
        "(operating_signatures.csv is OAT-binned, not timestamped)."
    )
    return cal, val, meta


def resolve_calibration_status(
    *,
    weather_mode: str,
    has_bills: bool,
    bills_pass_fail: str | None,
    validation_applied: bool,
    validation_pass_fail: str | None,
) -> str:
    """Map weather + bill gates to scorecard status enum."""
    if weather_mode == SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY:
        return STATUS_CONCEPTUAL_ONLY
    if not has_bills or bills_pass_fail in {
        None,
        "bills_recommended",
        "insufficient_data",
        "period_mismatch",
    }:
        return STATUS_CONCEPTUAL_ONLY
    if validation_applied:
        if validation_pass_fail == "pass":
            return STATUS_VALIDATED
        if validation_pass_fail == "fail":
            return STATUS_FAILED_VALIDATION
        return STATUS_CALIBRATED_NOT_VALIDATED
    return STATUS_CALIBRATED_NOT_VALIDATED


def run_calibration(
    bundle_dir: Path,
    *,
    seed_path: Path | None = None,
    dry_run: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    validation_months: int = 0,
    validation_start: int | None = None,
    area_scale_for_g14: float | None = None,
    publish_studio: bool = True,
    hard_size: dict[str, float] | None = None,
) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    # Accept WattLab dump zip as well as extracted folders
    if bundle.is_file() and bundle.suffix.lower() == ".zip":
        from wattlab.seed import load_bundle

        loaded = load_bundle(bundle)
        for name in ("model_seed.json", "weather_observed.csv", "operating_signatures.csv"):
            p = loaded.files.get(name)
            if p is not None:
                bundle = Path(p).parent
                break
        else:
            raise FileNotFoundError(
                f"WattLab dump zip missing model_seed/weather/signatures: {bundle_dir}"
            )

    seed_file = Path(seed_path) if seed_path else bundle / "model_seed.json"
    if not seed_file.is_file():
        raise FileNotFoundError(f"model_seed.json not found: {seed_file}")
    seed = _read_json(seed_file)

    weather_csv = bundle / "weather_observed.csv"
    sig_rows = _read_csv(bundle / "operating_signatures.csv")
    window = seed.get("data_window") or {}
    begin = window.get("start_utc")
    end = window.get("end_utc")
    if not begin or not end:
        raise ValueError("model_seed.data_window.start_utc/end_utc required")

    # Do NOT invent office/Chicago — block with NEEDS_INPUT for the agent/human.
    needed = []
    if seed.get("building_type") in (None, "", {}):
        needed.append("building_type")
    if seed.get("city") in (None, "", {}):
        needed.append("city")
    if seed.get("floor_area_ft2") in (None, "", 0, 0.0):
        needed.append("floor_area_ft2")
    if needed:
        raise ValueError(
            "NEEDS_INPUT: missing required seed fields "
            f"{needed}. Provide via wattlab twin --inputs or model_seed.json — "
            "do not invent office/Chicago defaults for a real building."
        )

    minimal = {
        k: seed[k]
        for k in (
            "building_type",
            "city",
            "code_year",
            "floor_area_ft2",
            "floors",
            "floor_to_floor_ft",
            "wwr",
            "hvac",
            "utility",
            "project_id",
            "display_name",
            "anonymized",
        )
        if seed.get(k) is not None
    }
    profile = resolve_profile(minimal)

    if lat is not None:
        lat_v = float(lat)
    elif seed.get("lat") is not None:
        lat_v = float(seed["lat"])
    else:
        raise ValueError(
            "NEEDS_INPUT: lat required for AMY EPW (pass --lat or set model_seed.lat)"
        )
    if lon is not None:
        lon_v = float(lon)
    elif seed.get("lon") is not None:
        lon_v = float(seed["lon"])
    else:
        raise ValueError(
            "NEEDS_INPUT: lon required for AMY EPW (pass --lon or set model_seed.lon)"
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = ARTIFACTS / f"calibrate_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    wx = weather_suitability(
        source="amy",
        epw_note="AMY EPW from weather_observed.csv (Open-Meteo / vibe19).",
        city_id=str(minimal.get("city") or ""),
    )

    plan = {
        "product": "OpenFDD WattLab Calibration",
        "run_id": run_id,
        "bundle": str(bundle),
        "seed": str(seed_file),
        "data_window": window,
        "lat": lat_v,
        "lon": lon_v,
        "weather_csv": str(weather_csv) if weather_csv.is_file() else None,
        "weather_suitability": wx,
        "validation_months": validation_months,
        "validation_start": validation_start,
        "artifacts_dir": str(run_dir),
    }
    if dry_run:
        plan["dry_run"] = True
        (run_dir / "calibration_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return plan

    if not weather_csv.is_file():
        raise FileNotFoundError(f"weather_observed.csv required for AMY EPW: {weather_csv}")

    epw_path = run_dir / "amy.epw"
    epw_meta = build_amy_epw(
        weather_csv,
        epw_path,
        lat=lat_v,
        lon=lon_v,
        location_name=str(seed.get("project_id") or "OpenFDD_AMY"),
    )

    proto_rel = (profile.get("energyplus") or {}).get("prototype_idf")
    proto = Path(proto_rel) if proto_rel else DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        proto = ROOT / proto_rel if proto_rel else DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        proto = DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        raise FileNotFoundError(f"Prototype IDF not found: {proto}")
    idf1 = run_dir / "cal_base.idf"
    apply_fan_avail_continuous(proto, idf1)
    idf2 = run_dir / "cal_runperiod.idf"
    rp_meta = apply_run_period(idf1, idf2, begin=begin, end=end)
    idf3 = run_dir / "cal_hourly.idf"
    out_meta = apply_hourly_outputs(idf2, idf3)
    from wattlab.energyplus.patches.hourly_outputs import apply_monthly_energy_tables

    idf4 = run_dir / "cal_ready.idf"
    monthly_meta = apply_monthly_energy_tables(idf3, idf4)
    sim_idf = idf4

    # Optional area-aware hard-size after a first autosize pass is handled below
    # when hard_size is set (freeze requires inventory from a completed sim).
    sim_dir = run_dir / "sim_calibrate"
    sim_dir.mkdir(parents=True, exist_ok=True)
    sim_result = simulate(sim_idf, epw_path, sim_dir)
    sizing_scenario = "autosize"
    if hard_size and isinstance(hard_size, dict) and (
        hard_size.get("cooling_tons") is not None or hard_size.get("fan_hp") is not None
    ):
        from wattlab.config import PROTOTYPE_AREA_FT2_NOMINAL
        from wattlab.energyplus.sizing import (
            freeze_autosized_values,
            nameplate_to_capacity_factors,
            parse_sizing_inventory,
        )

        inv = parse_sizing_inventory(sim_dir)
        area_ft2 = float(
            seed.get("conditioned_floor_area_ft2") or seed.get("floor_area_ft2") or 0
        )
        scale = area_ft2 / PROTOTYPE_AREA_FT2_NOMINAL if area_ft2 > 0 else None
        factors, factor_meta = nameplate_to_capacity_factors(
            inv,
            cooling_tons=(
                float(hard_size["cooling_tons"])
                if hard_size.get("cooling_tons") is not None
                else None
            ),
            fan_hp=(
                float(hard_size["fan_hp"]) if hard_size.get("fan_hp") is not None else None
            ),
            prototype_area_scale=scale,
        )
        if factor_meta.get("hard_size_refused"):
            sizing_scenario = "hard_size_refused"
        elif factors:
            hard_idf = run_dir / "cal_hard_size.idf"
            freeze_autosized_values(sim_idf, hard_idf, inv, capacity_factors=factors)
            sim_dir = run_dir / "sim_calibrate_hard"
            sim_dir.mkdir(parents=True, exist_ok=True)
            sim_idf = hard_idf
            sim_result = simulate(sim_idf, epw_path, sim_dir)
            sizing_scenario = "hard_size"
        else:
            sizing_scenario = "autosize_observe_hard_size_unavailable"

    annual = annual_from_output_dir(sim_dir)

    hourly = parse_eplusout_hourly(sim_dir)
    sim_sigs = simulated_signatures_from_hourly(hourly)
    obs_fan = aggregate_signatures(sig_rows, "fan")
    obs_cool = aggregate_signatures(sig_rows, "mech_cooling")
    fan_cmp = compare_signature_maps(obs_fan, sim_sigs.get("fan") or {})
    cool_cmp = compare_signature_maps(obs_cool, sim_sigs.get("mech_cooling") or {})

    alignment: dict[str, Any] | None = None
    try:
        from wattlab.weather.epw import load_weather_frame, resample_hourly

        wx_df = resample_hourly(load_weather_frame(weather_csv))
        obs_oat: list[float] = []
        series = wx_df["web-outside-air-temp"] if "web-outside-air-temp" in wx_df.columns else wx_df.iloc[:, 0]
        for v in series:
            try:
                obs_oat.append((float(v) - 32.0) * 5.0 / 9.0)
            except (TypeError, ValueError):
                obs_oat.append(float("nan"))
        sim_oat = [r.get("oat_c", float("nan")) for r in hourly]
        o = [x for x in obs_oat if not (isinstance(x, float) and math.isnan(x))]
        s = [x for x in sim_oat if not (isinstance(x, float) and math.isnan(x))]
        n2 = min(len(o), len(s))
        if n2 >= 24:
            alignment = detect_hour_shift(o[:n2], s[:n2], max_lag=3)
        else:
            alignment = {"warning": None, "note": "insufficient_hourly_overlap"}
    except Exception as exc:  # noqa: BLE001 — best-effort diagnostic
        alignment = {"warning": None, "note": f"alignment_skipped: {exc}"}

    bills = load_utility_bills(bundle, seed)
    cal_bills, val_bills, holdout_meta = split_bills_for_holdout(
        bills,
        validation_months=validation_months,
        validation_start=validation_start,
    )
    data_window = seed.get("data_window") if isinstance(seed.get("data_window"), dict) else None

    monthly_for_g14 = list(annual.get("monthly") or [])
    g14_scale_meta: dict[str, Any] = {"area_scale_applied": None, "mode": "prototype_raw"}
    if area_scale_for_g14 is not None and float(area_scale_for_g14) > 0:
        from wattlab.calibrate import scale_monthly_energy

        monthly_for_g14 = scale_monthly_energy(
            monthly_for_g14, area_scale=float(area_scale_for_g14)
        )
        g14_scale_meta = {
            "area_scale_applied": round(float(area_scale_for_g14), 4),
            "mode": "area_scaled_prototype",
            "note": (
                "Simulated monthly kWh/therms multiplied by prototype_area_scale "
                "for absolute G14 vs site bills. Unscaled 5Zone geometry — not site CAD."
            ),
        }

    bills_cmp: dict[str, Any]
    validation_cmp: dict[str, Any] | None = None
    if not bills:
        bills_cmp = {
            "months_compared": 0,
            "pass_fail": "bills_recommended",
            "note": "Upload monthly utility bills for ASHRAE-14 magnitude calibration.",
        }
    elif holdout_meta.get("applied"):
        bills_cmp = compare_bills_to_monthly(
            cal_bills, monthly_for_g14, data_window=data_window
        )
        bills_cmp["split"] = "calibration"
        validation_cmp = compare_bills_to_monthly(
            val_bills, monthly_for_g14, data_window=data_window
        )
        validation_cmp["split"] = "validation"
    else:
        bills_cmp = compare_bills_to_monthly(
            bills, monthly_for_g14, data_window=data_window
        )
    bills_cmp["g14_scale"] = g14_scale_meta
    if validation_cmp is not None:
        validation_cmp["g14_scale"] = g14_scale_meta

    if bills and bills_cmp.get("pass_fail") in {"pass", "fail"}:
        overall = bills_cmp["pass_fail"]
        if validation_cmp and validation_cmp.get("pass_fail") == "fail":
            overall = "fail"
    elif fan_cmp.get("bins_compared", 0) > 0:
        overall = "shape_ok" if fan_cmp["pass_fail"] != "insufficient_data" else "insufficient_data"
    else:
        overall = "insufficient_data"

    status = resolve_calibration_status(
        weather_mode=str(wx.get("mode") or ""),
        has_bills=bool(bills),
        bills_pass_fail=str(bills_cmp.get("pass_fail") or ""),
        validation_applied=bool(holdout_meta.get("applied")),
        validation_pass_fail=(
            str(validation_cmp.get("pass_fail")) if validation_cmp else None
        ),
    )

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    patch_names = ["fan_avail_continuous", "run_period", "hourly_outputs", "monthly_energy_tables"]
    if sizing_scenario.startswith("hard_size"):
        patch_names.append(sizing_scenario)
    manifest = build_run_manifest(
        run_id=run_id,
        run_dir=run_dir,
        idf_path=sim_idf,
        epw_path=epw_path,
        patches=[{"name": n} for n in patch_names],
        weather_suitability=wx,
        status="SUCCESS" if (isinstance(sim_result, dict) and sim_result.get("ok", True)) else "FAILED",
        started_at=started_at,
        finished_at=finished_at,
        extra={
            "product": "OpenFDD WattLab Calibration",
            "prototype_sha256": file_sha256(proto) if proto.is_file() else None,
            "calibration_status": status,
            "sizing_scenario": sizing_scenario,
        },
    )
    write_run_manifest(run_dir, manifest)

    scorecard = {
        "product": "OpenFDD WattLab Calibration",
        "run_id": run_id,
        "overall": overall,
        "status": status,
        "data_window": window,
        "weather_suitability": wx,
        "sizing_scenario": sizing_scenario,
        "hard_size": hard_size,
        "g14_scale": g14_scale_meta,
        "prototype_area_scale": (
            float(area_scale_for_g14) if area_scale_for_g14 else None
        ),
        "epw": epw_meta,
        "run_period": rp_meta,
        "hourly_outputs": out_meta,
        "monthly_energy_tables": monthly_meta,
        "alignment": alignment,
        "holdout": holdout_meta,
        "run_manifest": {
            "model_sha256": manifest.get("model_sha256"),
            "weather_sha256": manifest.get("weather_sha256"),
            "energyplus_version": manifest.get("energyplus_version"),
            "docker_image": manifest.get("docker_image"),
        },
        "simulate": {
            "ok": bool(sim_result.get("ok", True)) if isinstance(sim_result, dict) else True,
            "sim_dir": str(sim_dir),
        },
        "annual": {
            "electricity_kwh_year": annual.get("electricity_kwh_year"),
            "site_eui_kbtu_ft2_year": annual.get("site_eui_kbtu_ft2_year"),
            "peak_demand_kw": annual.get("peak_demand_kw"),
            "status": annual.get("status"),
            "monthly": annual.get("monthly") or [],
            "building_area_m2": annual.get("building_area_m2"),
        },
        "signatures": {
            "fan": fan_cmp,
            "mech_cooling": cool_cmp,
            "note": "Whole-window OAT-bin shape match (not split by calibration/validation months).",
        },
        "utility_bills": bills_cmp,
        "utility_bills_validation": validation_cmp,
        "thresholds_ashrae14_monthly": {"nmbe_pct": NMBE_PASS, "cvrmse_pct": CVRMSE_PASS},
        "artifacts_dir": str(run_dir),
        "profile_project_id": profile.get("project_id"),
    }
    out_json = run_dir / "calibration_scorecard.json"
    out_json.write_text(json.dumps(scorecard, indent=2, default=str), encoding="utf-8")
    scorecard["scorecard_path"] = str(out_json)

    if publish_studio:
        try:
            from wattlab.studio.ep_viz import publish_run_for_studio

            published = publish_run_for_studio(
                run_dir,
                run_id=f"calibrate_{run_id}",
                report={
                    **scorecard,
                    "result_records": [
                        {
                            "measure_id": None,
                            "annual": scorecard.get("annual") or {},
                            "monthly": (scorecard.get("annual") or {}).get("monthly") or [],
                        }
                    ],
                },
            )
            # Stamp for Twin EUI / scorecard autoload
            stamp = {
                "run_id": run_id,
                "calibration_status": status,
                "overall": overall,
                "pass_fail": bills_cmp.get("pass_fail"),
                "weather_mode": (wx or {}).get("mode"),
                "prototype_area_scale": scorecard.get("prototype_area_scale"),
                "sizing_scenario": sizing_scenario,
                "g14_scale": g14_scale_meta,
                "scorecard_path": str(out_json),
            }
            (published / "campaign_stamp.json").write_text(
                json.dumps(stamp, indent=2), encoding="utf-8"
            )
            shutil_copy = getattr(__import__("shutil"), "copy2")
            if out_json.is_file():
                shutil_copy(out_json, published / "calibration_scorecard.json")
            scorecard["studio_run_dir"] = str(published)
            try:
                from wattlab.deliverables import package_deliverables

                deliv_dir = ARTIFACTS / f"deliverable_calibrate_{run_id}"
                deliv = package_deliverables(
                    out_dir=deliv_dir,
                    run_dir=run_dir,
                    scorecard=scorecard,
                    report={
                        "run_id": run_id,
                        "prototype_area_scale": scorecard.get("prototype_area_scale"),
                        "weather_suitability": wx,
                        "sizing_scenario": sizing_scenario,
                        "area_honesty": (
                            "Area-scaled G14 uses prototype geometry × scale — not site CAD."
                        ),
                    },
                    profile=profile,
                )
                scorecard["deliverable"] = deliv
                if deliv.get("zip_path"):
                    shutil_copy(deliv["zip_path"], Path(published) / Path(deliv["zip_path"]).name)
            except Exception as exc:  # noqa: BLE001
                scorecard["deliverable_error"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            scorecard["studio_publish_error"] = str(exc)

    return scorecard


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Calibrate WattLab prototype against vibe19 model seed")
    p.add_argument("--bundle", type=Path, required=True, help="vibe19 export / model-seed bundle dir")
    p.add_argument("--seed", type=Path, default=None, help="Override model_seed.json path")
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lon", type=float, default=None)
    p.add_argument(
        "--validation-months",
        type=int,
        default=0,
        help="Hold out last N monthly bills for validation (needs >=6 months; 0=disabled)",
    )
    p.add_argument(
        "--validation-start",
        type=int,
        default=None,
        help="Optional calendar month (1-12) to start contiguous validation holdout",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        result = run_calibration(
            args.bundle,
            seed_path=args.seed,
            dry_run=args.dry_run,
            lat=args.lat,
            lon=args.lon,
            validation_months=args.validation_months,
            validation_start=args.validation_start,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
