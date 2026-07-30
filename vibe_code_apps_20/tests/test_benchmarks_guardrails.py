"""Units for the retrofit-cost registry and the ROI guardrail gate."""

from __future__ import annotations

from wattlab.benchmarks.costs import check_cost, load_registry, scope_for_measure
from wattlab.benchmarks.guardrails import gate_capital_plan
from wattlab.finance import capital_plan, measure_economics

AREA = 140_000.0
BASE_KWH = 1_464_449.0
BASE_THERMS = 43_626.0
EUI = 66.9


def _plan(cost: float, kwh: float, therms: float = 0.0, mid: str = "ECM-AHU-SCHED-ALIGN"):
    return capital_plan([
        measure_economics(
            measure_id=mid, implementation_cost_usd=cost,
            kwh_saved=kwh, therms_saved=therms,
        )
    ])


def test_cost_registry_has_all_scopes_with_basis_and_year():
    rows = load_registry()
    scopes = {r["scope"] for r in rows}
    assert {"rcx_tuning", "minor_hvac_controls", "major_hvac", "deep_retrofit",
            "windows_full_replacement", "windows_secondary",
            "controls_first", "major_hvac_renewal", "deep_electrification"} <= scopes
    for r in rows:
        assert r["unit_basis"] and r["currency_year"] and r["confidence"]
        assert r["lo"] <= r["p50"] <= r["hi"]


def test_scope_for_measure_hints():
    assert scope_for_measure("ECM-AHU-SCHED-ALIGN") == "rcx_tuning"
    assert scope_for_measure("ECM-GL36-AIRSIDE") == "bas_overlay"
    assert scope_for_measure("ECM-BOILER-SWAP") == "major_hvac"
    assert scope_for_measure("ECM-WINDOW-UPGRADE") == "windows_full_replacement"
    assert scope_for_measure("ECM-AWHP-SURROGATE") == "deep_electrification"
    assert scope_for_measure("mystery") == "rcx_tuning"


def test_check_cost_windows_uses_glazing_basis():
    cc = check_cost(cost_usd=298_075, scope="windows_full_replacement",
                    floor_area_ft2=50_000, glazing_area_ft2=7_500)
    assert cc["unit_basis"] == "glazing_ft2"
    assert cc["cost_per_unit"] == 39.74
    assert cc["band"] == "within_band"
    # No glazing area → cannot judge
    cc2 = check_cost(cost_usd=298_075, scope="windows_full_replacement", floor_area_ft2=50_000)
    assert cc2["band"] == "no_reference"


def test_gate_publishes_sane_controls_plan():
    # $8k schedule fix saving ~3% of baseline → clean PUBLISH
    gate = gate_capital_plan(
        _plan(8_000, kwh=80_000, therms=1_000),
        property_type="office", floor_area_ft2=AREA,
        baseline_kwh=BASE_KWH, baseline_therms=BASE_THERMS, site_eui_kbtu_ft2=EUI,
    )
    assert gate["verdict"] == "PUBLISH"
    assert gate["investigate_count"] == 0
    names = {c["check"] for c in gate["checks"]}
    assert {"baseline_eui_band", "savings_fraction", "post_retrofit_eui", "measure_cost_band"} <= names


def test_gate_flags_implausible_savings_fraction():
    # Controls measure claiming ~70% of whole-building energy
    gate = gate_capital_plan(
        _plan(8_000, kwh=1_000_000, therms=30_000),
        property_type="office", floor_area_ft2=AREA,
        baseline_kwh=BASE_KWH, baseline_therms=BASE_THERMS, site_eui_kbtu_ft2=EUI,
    )
    assert gate["verdict"] == "INVESTIGATE"
    flagged = {c["check"] for c in gate["checks"] if c["status"] == "investigate"}
    assert "savings_fraction" in flagged
    assert "payback_plausibility" in flagged  # ~$150k/yr savings on $8k cost


def test_gate_flags_cost_above_scope_band():
    # $2M "schedule alignment" on 140k ft2 = $14.3/ft2 vs rcx band hi $0.50
    gate = gate_capital_plan(
        _plan(2_000_000, kwh=80_000),
        property_type="office", floor_area_ft2=AREA,
        baseline_kwh=BASE_KWH, baseline_therms=BASE_THERMS, site_eui_kbtu_ft2=EUI,
    )
    flagged = {c["check"] for c in gate["checks"] if c["status"] == "investigate"}
    assert "measure_cost_band" in flagged


def test_gate_skips_gracefully_without_bills():
    gate = gate_capital_plan(
        _plan(8_000, kwh=80_000),
        property_type="office", floor_area_ft2=AREA,
    )
    statuses = {c["check"]: c["status"] for c in gate["checks"]}
    assert statuses["baseline_eui_band"] == "skipped"
    assert statuses["savings_fraction"] == "skipped"
    # Cost band still runs (needs only floor area) and passes here.
    assert gate["verdict"] == "PUBLISH"


def test_gate_flags_efficient_building_with_big_claims():
    # Baseline EUI already below office p20 (34) → investigate
    gate = gate_capital_plan(
        _plan(8_000, kwh=80_000),
        property_type="office", floor_area_ft2=AREA,
        baseline_kwh=BASE_KWH, baseline_therms=BASE_THERMS, site_eui_kbtu_ft2=25.0,
    )
    flagged = {c["check"] for c in gate["checks"] if c["status"] == "investigate"}
    assert "baseline_eui_band" in flagged
