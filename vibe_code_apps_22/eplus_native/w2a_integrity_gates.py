"""Expanded raw promotion gates for W2A integrity closure (fail-closed, no softening)."""
from __future__ import annotations

from typing import Any

from eplus_native.w2a_plant_knobs import plant_plausibility_check


# Predeclared ceilings / bands — do not soften to obtain a pass.
UTILITY_NMBE_ABS_MAX = 5.0
UTILITY_CVRMSE_MAX = 15.0
HOURLY_CVRMSE_MAX = 30.0  # aspirational; not GL14
HOURLY_NMBE_ABS_MAX = 10.0
PEAK_MAG_MAE_MEDIAN_MAX_KW = 40.0
HE05_09_MAE_MEDIAN_MAX_KW = 35.0
ZONE_MAE_MAX_F = 3.5
ZONE_BIAS_ABS_MAX_F = 2.5
UNMET_SUM_ZONE_HOURS_MAX = 5000.0
WEEKEND_RATIO_LO = 0.5
WEEKEND_RATIO_HI = 1.5


def integrity_promotion_gates(metrics: dict[str, Any], *, expanded_idf_text: str | None = None) -> dict[str, Any]:
    """Candidate passes only if ALL checks clear on reserved-final (and plant text)."""
    util = metrics.get("utility_monthly") or {}
    nmbe = util.get("nmbe_pct") if isinstance(util, dict) else None
    cv = util.get("cvrmse_pct") if isinstance(util, dict) else None
    util_ok = (
        nmbe is not None
        and cv is not None
        and abs(float(nmbe)) < UTILITY_NMBE_ABS_MAX
        and float(cv) < UTILITY_CVRMSE_MAX
    )

    reserved = metrics.get("reserved_final_winter_audit") or {}
    hourly = (reserved.get("hourly_score") if isinstance(reserved, dict) else None) or metrics.get(
        "hourly_score"
    ) or {}
    h_cv = hourly.get("cvrmse_pct")
    h_nmbe = hourly.get("nmbe_pct")
    hourly_ok = (
        h_cv is not None
        and float(h_cv) < HOURLY_CVRMSE_MAX
        and (h_nmbe is None or abs(float(h_nmbe)) < HOURLY_NMBE_ABS_MAX)
    )

    peaks = (reserved.get("day_level_peaks") if isinstance(reserved, dict) else None) or metrics.get(
        "day_level_peaks"
    ) or {}
    mag = (peaks.get("abs_peak_magnitude_error_kw") or {}).get("median")
    he = (peaks.get("morning_he05_09_mae_kw") or {}).get("median")
    peaks_ok = (
        mag is not None
        and he is not None
        and float(mag) <= PEAK_MAG_MAE_MEDIAN_MAX_KW
        and float(he) <= HE05_09_MAE_MEDIAN_MAX_KW
    )

    zones = metrics.get("six_zone_metrics") or {}
    zone_ok = True
    zone_detail: dict[str, Any] = {}
    if not zones:
        zone_ok = False
        zone_detail["reason"] = "missing_six_zone_metrics"
    else:
        for z, block in zones.items():
            if not isinstance(block, dict):
                zone_ok = False
                continue
            mae = block.get("mae")
            bias = block.get("bias")
            z_pass = (
                mae is not None
                and bias is not None
                and float(mae) <= ZONE_MAE_MAX_F
                and abs(float(bias)) <= ZONE_BIAS_ABS_MAX_F
            )
            zone_detail[z] = {"pass": z_pass, "mae": mae, "bias": bias}
            zone_ok = zone_ok and z_pass

    unmet = metrics.get("unmet_heating") or {}
    unmet_sum = unmet.get("sum_zone_unmet_heating_hours")
    unmet_ok = unmet_sum is not None and float(unmet_sum) <= UNMET_SUM_ZONE_HOURS_MAX

    st = metrics.get("structural") or {}
    ratio = st.get("weekend_collapse_ratio_mod_over_meas")
    struct_ok = ratio is not None and WEEKEND_RATIO_LO <= float(ratio) <= WEEKEND_RATIO_HI

    plant = metrics.get("plant_plausibility")
    if plant is None and expanded_idf_text is not None:
        plant = plant_plausibility_check(expanded_idf_text)
    plant_ok = bool((plant or {}).get("ok"))

    checks = {
        "utility_partial_period_screen": bool(util_ok),
        "utility_screen_label": "partial-period utility screen (not GL14)",
        "hourly_cvrmse_nmbe_aspirational": bool(hourly_ok),
        "hourly_not_called_gl14": True,
        "day_level_peaks_he05_09": bool(peaks_ok),
        "six_zone_mae_bias": bool(zone_ok),
        "unmet_heating_hours": bool(unmet_ok),
        "weekend_ratio_band": bool(struct_ok),
        "plant_plausibility": plant_ok,
    }
    all_pass = all(
        checks[k]
        for k in (
            "utility_partial_period_screen",
            "hourly_cvrmse_nmbe_aspirational",
            "day_level_peaks_he05_09",
            "six_zone_mae_bias",
            "unmet_heating_hours",
            "weekend_ratio_band",
            "plant_plausibility",
        )
    )
    return {
        **checks,
        "zone_detail": zone_detail,
        "plant_plausibility_detail": plant,
        "raw_eplus_gates_pass": all_pass,
        "dsm_eligible": False,
        "thresholds": {
            "utility_nmbe_abs_max": UTILITY_NMBE_ABS_MAX,
            "utility_cvrmse_max": UTILITY_CVRMSE_MAX,
            "hourly_cvrmse_max": HOURLY_CVRMSE_MAX,
            "hourly_nmbe_abs_max": HOURLY_NMBE_ABS_MAX,
            "peak_mag_mae_median_max_kw": PEAK_MAG_MAE_MEDIAN_MAX_KW,
            "he05_09_mae_median_max_kw": HE05_09_MAE_MEDIAN_MAX_KW,
            "zone_mae_max_f": ZONE_MAE_MAX_F,
            "zone_bias_abs_max_f": ZONE_BIAS_ABS_MAX_F,
            "unmet_sum_zone_hours_max": UNMET_SUM_ZONE_HOURS_MAX,
            "weekend_ratio": [WEEKEND_RATIO_LO, WEEKEND_RATIO_HI],
        },
        "nmbe_pct": nmbe,
        "cvrmse_pct": cv,
        "hourly_cvrmse_pct": h_cv,
        "weekend_ratio": ratio,
        "unmet_sum_zone_hours": unmet_sum,
    }
