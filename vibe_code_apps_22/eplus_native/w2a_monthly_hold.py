"""Monthly GL14-style hold helpers for W2A hourly dial-in."""
from __future__ import annotations

from typing import Any

from eplus_native.w2a_integrity_gates import UTILITY_CVRMSE_MAX, UTILITY_NMBE_ABS_MAX

C02_BASELINE_FEB_CVRMSE = 36.84633193377527
MONTHLY_HOLD_LABEL = (
    "partial-period utility / GL14-style screen (|NMBE|<5%, CVRMSE<15%); "
    "not purchased ASHRAE G14-2023"
)


def monthly_gl14_style_pass(utility_monthly: dict[str, Any] | None) -> dict[str, Any]:
    """Hard monthly constraint used for ranking eligibility."""
    util = utility_monthly or {}
    nmbe = util.get("nmbe_pct")
    cv = util.get("cvrmse_pct")
    ok = (
        nmbe is not None
        and cv is not None
        and abs(float(nmbe)) < UTILITY_NMBE_ABS_MAX
        and float(cv) < UTILITY_CVRMSE_MAX
    )
    return {
        "pass": bool(ok),
        "nmbe_pct": nmbe,
        "cvrmse_pct": cv,
        "nmbe_abs_max": UTILITY_NMBE_ABS_MAX,
        "cvrmse_max": UTILITY_CVRMSE_MAX,
        "label": MONTHLY_HOLD_LABEL,
    }


def rank_key_monthly_hold_hourly(trial: dict[str, Any]) -> tuple:
    """Lower is better. Monthly failures sort last."""
    hold = trial.get("monthly_hold") or {}
    if not hold.get("pass"):
        return (1, 1e9, 1e9, 1e9)
    m = trial.get("metrics") or {}
    feb = m.get("feb_cvrmse_pct")
    he = m.get("he05_09_mae_median")
    wk_err = m.get("weekend_abs_err")
    return (
        0,
        float(feb) if feb is not None else 1e9,
        float(he) if he is not None else 1e9,
        float(wk_err) if wk_err is not None else 1e9,
    )


def early_stop_no_feb_gain(
    monthly_passer_feb_cvs: list[float],
    *,
    baseline_feb_cv: float = C02_BASELINE_FEB_CVRMSE,
    streak: int = 3,
    min_improve_pt: float = 1.0,
) -> bool:
    """True if last `streak` monthly-passers each fail to beat baseline by ≥1 CV pt."""
    if len(monthly_passer_feb_cvs) < streak:
        return False
    recent = monthly_passer_feb_cvs[-streak:]
    return all((baseline_feb_cv - float(cv)) < min_improve_pt for cv in recent)
