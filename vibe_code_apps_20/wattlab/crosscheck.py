"""EnergyPlus-vs-proxy crosscheck — the twin-iterate loop's referee.

For each measure in an easy-button run, compare the EnergyPlus progressive
savings (``savings_by_measure`` rows) against the bench/ESCO proxy estimate
and emit a verdict:

- ``in_line``        — E+ within the agreement band of the proxy; trust it
- ``investigate``    — same sign but well outside the band; check assumptions
- ``keep_iterating`` — wrong sign or missing savings; the model needs work

Where monthly utility bills exist, the baseline is also gated against
ASHRAE Guideline 14 (monthly NMBE ±5%, CV(RMSE) ≤15%).

CLI: ``wattlab crosscheck --report artifacts/wattlab_.../wattlab_report.json
--proxies proxies.json`` where proxies.json maps measure_id to
``{"savings_kwh": ..., "savings_therms": ...}`` (a bench run output works
after reshaping).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from wattlab.bench.benchmark import calibration_metrics

G14_NMBE_LIMIT_PCT = 5.0
G14_CVRMSE_LIMIT_PCT = 15.0
DEFAULT_AGREEMENT_BAND = (0.5, 2.0)
"""E+/proxy savings ratio considered "in line" (screening-grade tolerance)."""


FT2_PER_M2 = 10.7639


def prototype_area_scale(
    *,
    target_ft2: float | None,
    model_area_m2: float | None,
) -> float | None:
    """Target-building ft2 divided by simulated-model ft2 (None if unknown).

    Returns None when either area is missing/zero so callers can fall back to
    unscaled comparison rather than guessing.
    """
    if not target_ft2 or not model_area_m2:
        return None
    model_ft2 = float(model_area_m2) * FT2_PER_M2
    if model_ft2 <= 0 or float(target_ft2) <= 0:
        return None
    return float(target_ft2) / model_ft2


def _hint(ratio: float | None, ep_kwh: float | None, proxy_kwh: float | None) -> str:
    if ep_kwh is None:
        return "EnergyPlus savings missing — check the measure simulated and parsed."
    if proxy_kwh is None:
        return "No proxy estimate — add a bench/ESCO calculation for this measure."
    if ratio is None:
        return "Proxy predicts ~zero savings — confirm the measure applies to this building."
    if ratio < 1.0:
        return (
            "EnergyPlus shows less savings than the ESCO proxy — check schedules, "
            "equipment sizing, and that the measure patch actually changed the model."
        )
    return (
        "EnergyPlus shows more savings than the ESCO proxy — check baseline "
        "inefficiency assumptions (fan power, minimum flows, setpoints)."
    )


def crosscheck_measure(
    *,
    measure_id: str,
    ep_savings_kwh: float | None,
    proxy_savings_kwh: float | None,
    ep_savings_therms: float | None = None,
    proxy_savings_therms: float | None = None,
    agreement_band: tuple[float, float] = DEFAULT_AGREEMENT_BAND,
    area_scale: float | None = None,
) -> dict[str, Any]:
    """Verdict for one measure from E+ vs proxy annual savings.

    ``area_scale`` normalizes for prototype-vs-target floor area (target ft2 /
    model ft2). The bundled 5ZoneAirCooled prototype is only ~5k ft2, so an E+
    run for a 140k ft2 profile under-reports absolute savings ~28x unless
    scaled — discovered live in the Liberty twin-loop rehearsal.
    """
    lo, hi = agreement_band
    scaled_kwh = ep_savings_kwh
    scaled_therms = ep_savings_therms
    if area_scale is not None and area_scale > 0:
        if ep_savings_kwh is not None:
            scaled_kwh = ep_savings_kwh * area_scale
        if ep_savings_therms is not None:
            scaled_therms = ep_savings_therms * area_scale
    ratio: float | None = None
    if (
        scaled_kwh is not None
        and proxy_savings_kwh is not None
        and abs(proxy_savings_kwh) > 1e-9
    ):
        ratio = scaled_kwh / proxy_savings_kwh

    if scaled_kwh is None or proxy_savings_kwh is None:
        verdict = "investigate"
    elif ratio is None:
        verdict = "investigate"
    elif ratio <= 0:
        verdict = "keep_iterating"
    elif lo <= ratio <= hi:
        verdict = "in_line"
    else:
        verdict = "investigate"

    out: dict[str, Any] = {
        "measure_id": measure_id,
        "ep_savings_kwh": ep_savings_kwh,
        "proxy_savings_kwh": proxy_savings_kwh,
        "agreement_ratio": None if ratio is None else round(ratio, 3),
        "agreement_band": list(agreement_band),
        "verdict": verdict,
    }
    if area_scale is not None:
        out["area_scale"] = round(area_scale, 3)
        out["ep_savings_kwh_scaled"] = None if scaled_kwh is None else round(scaled_kwh, 1)
    if ep_savings_therms is not None or proxy_savings_therms is not None:
        out["ep_savings_therms"] = ep_savings_therms
        out["proxy_savings_therms"] = proxy_savings_therms
        if area_scale is not None and scaled_therms is not None:
            out["ep_savings_therms_scaled"] = round(scaled_therms, 1)
    if verdict != "in_line":
        out["hint"] = _hint(ratio, scaled_kwh, proxy_savings_kwh)
    return out


def g14_gates(
    actual_monthly: list[float],
    modeled_monthly: list[float],
) -> dict[str, Any]:
    """ASHRAE Guideline 14 monthly gates against utility bills."""
    metrics = calibration_metrics(actual_monthly, modeled_monthly)
    nmbe_ok = abs(metrics["nmbe_percent"]) <= G14_NMBE_LIMIT_PCT
    cvrmse_ok = metrics["cvrmse_percent"] <= G14_CVRMSE_LIMIT_PCT
    return {
        "nmbe_percent": round(metrics["nmbe_percent"], 2),
        "cvrmse_percent": round(metrics["cvrmse_percent"], 2),
        "nmbe_limit_pct": G14_NMBE_LIMIT_PCT,
        "cvrmse_limit_pct": G14_CVRMSE_LIMIT_PCT,
        "nmbe_pass": nmbe_ok,
        "cvrmse_pass": cvrmse_ok,
        "calibrated": nmbe_ok and cvrmse_ok,
        "n_months": metrics["n"],
    }


def crosscheck_report(
    savings_rows: list[dict[str, Any]],
    proxy_by_measure: dict[str, dict[str, Any]],
    *,
    bills_monthly_kwh: list[float] | None = None,
    baseline_monthly_kwh: list[float] | None = None,
    agreement_band: tuple[float, float] = DEFAULT_AGREEMENT_BAND,
    area_scale: float | None = None,
) -> dict[str, Any]:
    """Full crosscheck block from an easy-button ``savings_by_measure`` table.

    ``proxy_by_measure`` maps measure_id to ``{"savings_kwh", "savings_therms"?}``.
    Incremental (vs previous step) E+ savings are compared, matching how each
    ESCO proxy prices a single measure. ``area_scale`` (target ft2 / model ft2)
    normalizes prototype-sized E+ savings before comparing to proxies sized
    for the real building.
    """
    measures: list[dict[str, Any]] = []
    for row in savings_rows:
        mid = str(row.get("measure_id") or "")
        if not mid or mid == "baseline":
            continue
        proxy = proxy_by_measure.get(mid) or {}
        vs_prev = row.get("vs_previous") or {}
        measures.append(
            crosscheck_measure(
                measure_id=mid,
                ep_savings_kwh=vs_prev.get("kwh_saved"),
                proxy_savings_kwh=proxy.get("savings_kwh"),
                ep_savings_therms=vs_prev.get("therms_saved"),
                proxy_savings_therms=proxy.get("savings_therms"),
                agreement_band=agreement_band,
                area_scale=area_scale,
            )
        )

    verdicts = [m["verdict"] for m in measures]
    overall = (
        "in_line"
        if measures and all(v == "in_line" for v in verdicts)
        else ("keep_iterating" if "keep_iterating" in verdicts else ("investigate" if measures else "no_proxies"))
    )

    out: dict[str, Any] = {
        "overall_verdict": overall,
        "measures": measures,
        "unmatched_proxies": sorted(
            set(proxy_by_measure) - {m["measure_id"] for m in measures}
        ),
    }
    if bills_monthly_kwh and baseline_monthly_kwh:
        modeled = list(baseline_monthly_kwh)
        if area_scale is not None and area_scale > 0:
            modeled = [v * area_scale for v in modeled]
        try:
            out["g14"] = g14_gates(bills_monthly_kwh, modeled)
            if area_scale is not None:
                out["g14"]["area_scale_applied"] = round(area_scale, 3)
        except ValueError as exc:
            out["g14"] = {"error": str(exc)}
    return out


def crosscheck_from_report(
    report: dict[str, Any],
    proxy_by_measure: dict[str, dict[str, Any]],
    *,
    bills_monthly_kwh: list[float] | None = None,
) -> dict[str, Any]:
    """Crosscheck straight from a ``wattlab_report.json`` payload."""
    savings_rows = report.get("savings_by_measure") or []
    baseline_monthly: list[float] | None = None
    records = report.get("result_records") or []
    if records:
        monthly = records[0].get("monthly") or []
        vals = [m.get("electricity_kwh") for m in monthly if m.get("electricity_kwh") is not None]
        if vals:
            baseline_monthly = [float(v) for v in vals]
    return crosscheck_report(
        savings_rows,
        proxy_by_measure,
        bills_monthly_kwh=bills_monthly_kwh,
        baseline_monthly_kwh=baseline_monthly,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab crosscheck",
        description="Compare EnergyPlus measure savings against bench/ESCO proxies",
    )
    p.add_argument("--report", type=Path, required=True, help="wattlab_report.json from easy-button")
    p.add_argument(
        "--proxies",
        type=Path,
        required=True,
        help="JSON mapping measure_id -> {savings_kwh, savings_therms?}",
    )
    p.add_argument(
        "--bills",
        type=Path,
        default=None,
        help="Optional JSON list of 12 monthly kWh bills for G14 gates",
    )
    p.add_argument("--out", type=Path, default=None, help="Write crosscheck JSON here")
    args = p.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    proxies = json.loads(args.proxies.read_text(encoding="utf-8"))
    bills = json.loads(args.bills.read_text(encoding="utf-8")) if args.bills else None

    result = crosscheck_from_report(report, proxies, bills_monthly_kwh=bills)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result.get("overall_verdict") in {"in_line", "no_proxies"} else 1


if __name__ == "__main__":
    sys.exit(main())
