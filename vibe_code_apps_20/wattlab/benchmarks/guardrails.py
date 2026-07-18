"""Benchmark gate ahead of ROI publication.

If a proposed capital plan claims savings or costs far outside the benchmark
envelope, the run must not quietly emit a glossy ROI chart. This module scores
each check as ``ok`` / ``investigate`` and rolls them into an overall verdict
(``PUBLISH`` / ``INVESTIGATE``) with human-readable reasons, mirroring the
crosscheck module's verdict style.

Checks:
- baseline site EUI vs peer-group band (``wattlab.benchmarks.eui``)
- claimed total savings as a fraction of baseline consumption
- post-retrofit EUI implied by claimed savings vs the peer band floor
- per-measure implementation cost vs scope reference band
  (``wattlab.benchmarks.costs``)
- simple payback plausibility per cost scope
"""

from __future__ import annotations

from typing import Any

from wattlab.benchmarks import costs as costs_mod
from wattlab.benchmarks import eui as eui_mod
from wattlab.benchmarks.meters import KBTU_PER_KWH

KBTU_PER_THERM = 100.0

# A controls-only plan claiming more than this fraction of whole-building use
# is suspicious; deep retrofits can legitimately go higher.
MAX_SAVINGS_FRACTION = {
    "rcx_tuning": 0.25,
    "minor_hvac_controls": 0.30,
    "bas_overlay": 0.30,
    "major_hvac": 0.40,
    "non_energy_capital": 0.40,
    "windows_full_replacement": 0.30,
    "windows_secondary": 0.25,
    "deep_retrofit": 0.70,
}

# Paybacks under ~0.3yr on capital scopes usually mean a cost was forgotten.
MIN_PLAUSIBLE_PAYBACK_YEARS = {
    "rcx_tuning": 0.1,
    "minor_hvac_controls": 0.3,
    "bas_overlay": 0.5,
    "major_hvac": 1.0,
    "deep_retrofit": 2.0,
}


def _check(name: str, status: str, detail: str, **data: Any) -> dict[str, Any]:
    return {"check": name, "status": status, "detail": detail, **data}


def gate_capital_plan(
    plan: dict[str, Any],
    *,
    property_type: str,
    floor_area_ft2: float,
    baseline_kwh: float | None = None,
    baseline_therms: float | None = None,
    site_eui_kbtu_ft2: float | None = None,
    glazing_area_ft2: float | None = None,
) -> dict[str, Any]:
    """Run every benchmark guardrail against a ``wattlab.finance`` capital plan.

    Returns ``{"verdict": "PUBLISH"|"INVESTIGATE", "checks": [...],
    "investigate_count": n}``. Missing context (no bills, no EUI) downgrades
    checks to ``skipped`` rather than blocking.
    """
    checks: list[dict[str, Any]] = []
    measures = plan.get("measures") or []

    # -- baseline EUI vs peer group ---------------------------------------
    eui_cmp: dict[str, Any] | None = None
    if site_eui_kbtu_ft2 is not None and floor_area_ft2 > 0:
        eui_cmp = eui_mod.compare_eui(site_eui_kbtu_ft2, property_type)
        if eui_cmp["band"] == "within_band":
            status, detail = "ok", (
                f"Baseline site EUI {eui_cmp['site_eui_kbtu_ft2']} kBtu/ft2 is within the "
                f"{eui_cmp['property_type']} band ({eui_cmp['p20']}-{eui_cmp['p80']})."
            )
        elif eui_cmp["band"] == "above_p80":
            status, detail = "ok", (
                f"Baseline EUI {eui_cmp['site_eui_kbtu_ft2']} is above the p80 "
                f"({eui_cmp['p80']}) — high savings potential, but verify the meter "
                "allocation and floor area before trusting large claims."
            )
        else:
            status, detail = "investigate", (
                f"Baseline EUI {eui_cmp['site_eui_kbtu_ft2']} is below the p20 "
                f"({eui_cmp['p20']}) for {eui_cmp['property_type']} — an already-efficient "
                "building rarely supports big savings claims; check area/allocation."
            )
        checks.append(_check("baseline_eui_band", status, detail, **eui_cmp))
    else:
        checks.append(_check("baseline_eui_band", "skipped", "No site EUI provided (load bills first)."))

    # -- claimed savings fraction + implied post-retrofit EUI -------------
    tot_kwh = sum(float(m.get("kwh_saved") or 0.0) for m in measures)
    tot_therms = sum(float(m.get("therms_saved") or 0.0) for m in measures)
    scopes = [costs_mod.scope_for_measure(str(m.get("measure_id"))) for m in measures]
    dominant_scope = max(scopes, key=lambda s: MAX_SAVINGS_FRACTION.get(s, 0.3)) if scopes else "rcx_tuning"
    max_frac = MAX_SAVINGS_FRACTION.get(dominant_scope, 0.3)

    if baseline_kwh or baseline_therms:
        base_kbtu = (baseline_kwh or 0.0) * KBTU_PER_KWH + (baseline_therms or 0.0) * KBTU_PER_THERM
        saved_kbtu = tot_kwh * KBTU_PER_KWH + tot_therms * KBTU_PER_THERM
        frac = saved_kbtu / base_kbtu if base_kbtu > 0 else 0.0
        if frac > max_frac:
            checks.append(_check(
                "savings_fraction", "investigate",
                f"Plan claims {frac:.0%} of baseline site energy; more than {max_frac:.0%} is "
                f"implausible for scope '{dominant_scope}'. Tighten proxies or fix the model.",
                savings_fraction=round(frac, 3), max_fraction=max_frac, scope=dominant_scope,
            ))
        else:
            checks.append(_check(
                "savings_fraction", "ok",
                f"Plan claims {frac:.0%} of baseline site energy (limit {max_frac:.0%} for '{dominant_scope}').",
                savings_fraction=round(frac, 3), max_fraction=max_frac, scope=dominant_scope,
            ))

        if eui_cmp is not None and floor_area_ft2 > 0:
            post_eui = float(site_eui_kbtu_ft2) - saved_kbtu / floor_area_ft2
            floor = eui_cmp["p20"] * 0.5
            if post_eui < floor:
                checks.append(_check(
                    "post_retrofit_eui", "investigate",
                    f"Implied post-retrofit EUI {post_eui:.1f} kBtu/ft2 is below half the peer p20 "
                    f"({eui_cmp['p20']}) — the claimed savings would make this building a national "
                    "outlier. A human should challenge this.",
                    post_retrofit_eui=round(post_eui, 1), peer_p20=eui_cmp["p20"],
                ))
            else:
                checks.append(_check(
                    "post_retrofit_eui", "ok",
                    f"Implied post-retrofit EUI {post_eui:.1f} kBtu/ft2 stays plausible.",
                    post_retrofit_eui=round(post_eui, 1), peer_p20=eui_cmp["p20"],
                ))
    else:
        checks.append(_check("savings_fraction", "skipped", "No baseline consumption provided (load bills first)."))

    # -- per-measure cost bands + payback plausibility ---------------------
    for m in measures:
        mid = str(m.get("measure_id"))
        scope = costs_mod.scope_for_measure(mid)
        cost = float(m.get("implementation_cost_usd") or 0.0)
        cc = costs_mod.check_cost(
            cost_usd=cost, scope=scope, floor_area_ft2=floor_area_ft2,
            glazing_area_ft2=glazing_area_ft2,
        )
        if cc["band"] == "above_band":
            checks.append(_check(
                "measure_cost_band", "investigate",
                f"{mid}: ${cc['cost_per_unit']}/{cc['unit_basis']} is above the '{scope}' reference band "
                f"(${cc['ref_lo']}-{cc['ref_hi']}, {cc['currency_year']}$, {cc['confidence']} confidence).",
                measure_id=mid, **cc,
            ))
        elif cc["band"] in ("within_band", "below_band"):
            checks.append(_check(
                "measure_cost_band", "ok",
                f"{mid}: ${cc.get('cost_per_unit', 0)}/{cc.get('unit_basis', '?')} vs '{scope}' band "
                f"${cc.get('ref_lo')}-{cc.get('ref_hi')} ({cc.get('currency_year')}$).",
                measure_id=mid, **cc,
            ))

        pb = m.get("simple_payback_years")
        min_pb = MIN_PLAUSIBLE_PAYBACK_YEARS.get(scope)
        if pb is not None and min_pb is not None and cost > 0 and float(pb) < min_pb:
            checks.append(_check(
                "payback_plausibility", "investigate",
                f"{mid}: {float(pb):.2f}-yr payback is implausibly fast for scope '{scope}' "
                f"(floor {min_pb} yr) — was the full installed cost captured?",
                measure_id=mid, payback_years=float(pb), floor_years=min_pb, scope=scope,
            ))

    n_bad = sum(1 for c in checks if c["status"] == "investigate")
    return {
        "verdict": "INVESTIGATE" if n_bad else "PUBLISH",
        "investigate_count": n_bad,
        "checks": checks,
    }
