"""Agent twin-loop rehearsal: pretend Liberty Building 100 is a live project.

Plays the exact workflow an AI agent runs with a human (see
vibe20_agent_spec/docs/TWIN_LOOP.md):

  1. benchmark the bills (Liberty campus, shared electric split as scenario)
  2. resolve a building profile from minimal inputs
  3. price ESCO proxy savings for the chosen measure set
  4. run EnergyPlus baseline + progressive ECMs in Docker (real sims)
  5. crosscheck E+ vs proxy + G14 vs allocated bills
  6. roll a capital plan with benchmark-quoted costs
  7. gate the plan against benchmark guardrails

Requires Docker running with the energyplus-mcp-dev image built.
Run:  python scripts/agent_twin_demo.py [--measure-set best]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wattlab.config import ARTIFACTS  # noqa: E402
from wattlab.benchmarks import Campus, annual_summary, compare_eui  # noqa: E402
from wattlab.benchmarks.costs import lookup as cost_lookup, scope_for_measure  # noqa: E402
from wattlab.benchmarks.guardrails import gate_capital_plan  # noqa: E402
from wattlab.defaults import resolve_profile  # noqa: E402
from wattlab.easy_button import run_easy_button  # noqa: E402
from wattlab.finance import capital_plan, measure_economics  # noqa: E402

LIBERTY = ROOT / "examples" / "liberty" / "campus.json"
BUILDING_ID = "liberty_100"
FLOOR_AREA_FT2 = 140_000.0


def monthly_allocated_kwh(campus: Campus, summary: dict) -> list[float]:
    """Liberty 100's share of the shared electric meter, month by month."""
    w = summary["window"]
    b100 = next(b for b in summary["buildings"] if b["building_id"] == BUILDING_ID)
    share = b100["kwh"] / summary["campus"]["kwh"]  # area_weighted 50/50 -> 0.5
    frame = campus.monthly_frame()
    elec = frame[frame["fuel"] == "electricity"]
    months = sorted(m for m in elec["month"].unique() if w["start"] <= m <= w["end"])
    return [
        float(elec[elec["month"] == m]["usage"].sum()) * share
        for m in months
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure-set", default="best", choices=["good", "better", "best"])
    args = ap.parse_args(argv)

    # 1) Benchmark the bills -------------------------------------------------
    campus = Campus.from_json(LIBERTY)
    summary = annual_summary(campus, allocation="area_weighted")
    b100 = next(b for b in summary["buildings"] if b["building_id"] == BUILDING_ID)
    peer = compare_eui(b100["site_eui_kbtu_ft2"], b100["property_type"])
    print(f"[1 benchmark] {BUILDING_ID}: site EUI {b100['site_eui_kbtu_ft2']} "
          f"kBtu/ft2 vs peer p50 {peer['p50']} -> band {peer['band']}")

    # 2) Resolve profile from minimal inputs ---------------------------------
    profile = resolve_profile({
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": FLOOR_AREA_FT2,
        "floors": 4,
        "project_id": "WATTLAB-LIBERTY-100",
        "display_name": "Liberty Building 100 (rehearsal)",
        "measure_set": args.measure_set,
    })
    wxnote = profile["energyplus"]["epw_note"]
    print(f"[2 profile] city={profile['climate_city']} zone={profile['climate_zone']} "
          f"epw_note={wxnote[:60]}...")

    # 3) ESCO proxy savings for the measure set ------------------------------
    sys.path.insert(0, str(ROOT))
    from studio import estimate_proxy_savings
    from wattlab.measures.measure_sets import expand_measure_set

    measures = expand_measure_set(args.measure_set)
    mids = [m["measure_id"] for m in measures]
    proxies = estimate_proxy_savings(profile, mids)
    profile["proxy_savings"] = proxies
    print(f"[3 proxies] {json.dumps(proxies)}")

    # 4+5) EnergyPlus baseline + ECMs, crosscheck inside the report ----------
    bills = monthly_allocated_kwh(campus, summary)
    profile.setdefault("utility", {})["bills_monthly_kwh"] = bills
    report = run_easy_button(profile=profile, measure_set=args.measure_set)
    ok = all(r.get("status") == "COMPLETE" for r in report["result_records"])
    print(f"[4 energyplus] {len(report['result_records'])} sims complete={ok} "
          f"run_dir={report['artifacts_dir']}")
    baseline = report["result_records"][0]["annual"]
    print(f"    baseline: {baseline['electricity_kwh_year']:,.0f} kWh, "
          f"EUI {baseline['site_eui_kbtu_ft2_year']} kBtu/ft2")
    cc = report.get("crosscheck") or {}
    print(f"[5 crosscheck] overall={cc.get('overall_verdict')}")
    for m in cc.get("measures") or []:
        scaled = m.get("ep_savings_kwh_scaled", m["ep_savings_kwh"])
        print(f"    {m['measure_id']}: E+ {m['ep_savings_kwh']} kWh "
              f"(scaled {scaled}, x{m.get('area_scale')}) vs proxy "
              f"{m['proxy_savings_kwh']} -> {m['verdict']}")
    if "g14" in cc:
        print(f"    g14: {json.dumps(cc['g14'])}")

    # 6) Capital plan with benchmark-quoted costs ----------------------------
    # Use area-normalized E+ savings from the crosscheck (the raw prototype is
    # ~5k ft2; unscaled kWh would understate a 140k ft2 building ~28x).
    elec_rate = profile["utility"]["elec_usd_per_kwh"]
    gas_rate = profile["utility"]["gas_usd_per_therm"]
    cc_by_mid = {m["measure_id"]: m for m in cc.get("measures") or []}
    rows = []
    for srow in report["savings_by_measure"]:
        mid = srow.get("measure_id")
        if not mid or mid == "baseline":
            continue
        scope = scope_for_measure(mid)
        band = cost_lookup(scope) or {}
        usd_ft2 = float(band.get("p50_usd_per_unit") or 0.5)
        ccm = cc_by_mid.get(mid) or {}
        vs_prev = srow.get("vs_previous") or {}
        kwh = float(ccm.get("ep_savings_kwh_scaled")
                    or vs_prev.get("kwh_saved") or 0.0)
        therms = float(ccm.get("ep_savings_therms_scaled")
                       or vs_prev.get("therms_saved") or 0.0)
        rows.append(measure_economics(
            measure_id=mid,
            implementation_cost_usd=usd_ft2 * FLOOR_AREA_FT2,
            kwh_saved=kwh,
            therms_saved=therms,
            elec_rate_usd_per_kwh=elec_rate,
            gas_rate_usd_per_therm=gas_rate,
        ))
    plan = capital_plan(rows)
    t = plan["totals"]
    print(f"[6 capital plan] cost ${t['implementation_cost_usd']:,.0f}, "
          f"saves ${t['annual_cost_saved_usd']:,.0f}/yr, "
          f"blended payback {t['blended_simple_payback_years']} yr")

    # 7) Benchmark guardrail gate --------------------------------------------
    gate = gate_capital_plan(
        plan,
        property_type="office",
        floor_area_ft2=FLOOR_AREA_FT2,
        baseline_kwh=b100["kwh"],
        baseline_therms=b100["mcf"] * 10.37,
        site_eui_kbtu_ft2=b100["site_eui_kbtu_ft2"],
    )
    print(f"[7 gate] verdict={gate['verdict']}")
    for c in gate["checks"]:
        print(f"    {c['check']}: {c['status']} - {c.get('detail','')[:90]}")

    out = ARTIFACTS / "agent_twin_demo_report.json"
    out.write_text(json.dumps(
        {"benchmark": summary, "peer": peer, "crosscheck": cc,
         "capital_plan": plan, "gate": gate,
         "report_dir": report["artifacts_dir"]}, indent=2), encoding="utf-8")
    print(f"[done] full artifact: {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
