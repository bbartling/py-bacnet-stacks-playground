"""Uncertainty helpers — tornado + weighted representative-day bands."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence


def weighted_annual_from_days(
    day_values_usd: Mapping[str, float],
    weights: Mapping[str, float],
) -> dict[str, float]:
    """Annualize with explicit day-type weights (must sum ~1.0 * 365 or to days/year).

    ``weights[day]`` = number of days/year represented by that day type.
    """
    missing = set(day_values_usd) - set(weights)
    if missing:
        raise ValueError(f"missing weights for day types: {sorted(missing)}")
    annual = 0.0
    weight_sum = 0.0
    for key, value in day_values_usd.items():
        w = float(weights[key])
        annual += float(value) * w
        weight_sum += w
    return {
        "annual_usd": float(annual),
        "weight_sum_days": float(weight_sum),
        "mean_usd_per_weighted_day": float(annual / weight_sum) if weight_sum else 0.0,
    }


def percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        raise ValueError("empty sample")
    if not 0.0 <= p <= 100.0:
        raise ValueError("percentile must be in [0, 100]")
    xs = list(sorted_vals)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return float(xs[f])
    return float(xs[f] + (xs[c] - xs[f]) * (k - f))


def distribution_bands(samples_usd: Sequence[float]) -> dict[str, float]:
    xs = sorted(float(v) for v in samples_usd)
    return {
        "n": float(len(xs)),
        "p10_usd": percentile(xs, 10),
        "p50_usd": percentile(xs, 50),
        "p90_usd": percentile(xs, 90),
        "mean_usd": float(sum(xs) / len(xs)),
        "min_usd": float(xs[0]),
        "max_usd": float(xs[-1]),
    }


def tornado_one_at_a_time(
    base_params: Mapping[str, float],
    *,
    evaluate: Callable[[Mapping[str, float]], float],
    low_mult: float = 0.8,
    high_mult: float = 1.2,
) -> dict[str, Any]:
    """OAT tornado: each param ±20% (or absolute if base is 0)."""
    base_val = float(evaluate(dict(base_params)))
    bars: list[dict[str, float | str]] = []
    for key, base in base_params.items():
        b = float(base)
        low_p = dict(base_params)
        high_p = dict(base_params)
        if abs(b) < 1e-12:
            low_p[key] = -0.1
            high_p[key] = 0.1
        else:
            low_p[key] = b * low_mult
            high_p[key] = b * high_mult
        low_v = float(evaluate(low_p))
        high_v = float(evaluate(high_p))
        bars.append(
            {
                "param": key,
                "low_usd": low_v,
                "high_usd": high_v,
                "swing_usd": abs(high_v - low_v),
                "base_usd": base_val,
            }
        )
    bars.sort(key=lambda row: float(row["swing_usd"]), reverse=True)
    return {
        "schema": "vibe23.tornado.v1",
        "claim": "ILLUSTRATIVE_OAT",
        "base_usd": base_val,
        "bars": bars,
    }


def default_day_type_weights() -> dict[str, float]:
    """Explicit representative-day weights (not 365× extreme day)."""
    return {
        "summer_hot": 30.0,
        "summer_typical": 90.0,
        "winter_design": 10.0,
        "winter_typical": 80.0,
        "shoulder": 155.0,
    }
