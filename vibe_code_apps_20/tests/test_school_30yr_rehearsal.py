"""Tests for the school 30-year deep-retrofit rehearsal (Task 4).

TDD: written before examples/school_30yr, the school_30yr_* measure sets, and
scripts/school_30yr_rehearsal.py existed. No network and no Docker anywhere in
this file — weather uses an injected opener with API-shaped bytes and the
easy-button runner is a fake. The live Open-Meteo + Docker path is exercised
by the opt-in integration test at the bottom (RUN_SCHOOL_30YR_LIVE=1).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (str(ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import school_30yr_rehearsal as rehearsal  # noqa: E402
from wattlab.benchmarks.costs import scope_for_measure  # noqa: E402
from wattlab.config import (  # noqa: E402
    ACTUAL_YEAR_CALIBRATION,
    SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
    weather_suitability,
)
from wattlab.contracts import (  # noqa: E402
    EPW_REQUIRED_VARIABLES,
    RetrofitScenario,
    UtilityDataset,
    WeatherDatasetMeta,
)
from wattlab.energyplus.results import savings_by_measure  # noqa: E402
from wattlab.finance import measure_economics  # noqa: E402
from wattlab.measures.measure_sets import (  # noqa: E402
    expand_measure_set,
    list_measure_sets,
)

CAMPUS = ROOT / "examples" / "school_30yr" / "campus.json"

HYDRONIC_IDS = [
    "ECM-AHU-SCHED-ALIGN",
    "ECM-PREMIUM-FAN-VFD",
    "ECM-CHILLER-REPLACE-HIEFF",
    "ECM-CONDENSING-BOILER",
    "ECM-WINDOW-HP-GLAZING",
]
ELECTRIFY_IDS = [
    "ECM-AHU-SCHED-ALIGN",
    "ECM-PREMIUM-FAN-VFD",
    "ECM-CHILLER-REPLACE-HIEFF",
    "ECM-AWHP-SURROGATE",
    "ECM-WINDOW-HP-GLAZING",
]


# ---------------------------------------------------------------------------
# Measure-set expansion + dynamic CLI choices
# ---------------------------------------------------------------------------


class TestMeasureSetExpansion:
    def test_hydronic_set_expands_ordered_and_approved(self):
        measures = expand_measure_set("school_30yr_hydronic")
        assert [m["measure_id"] for m in measures] == HYDRONIC_IDS
        assert all(m.get("review_status") == "approved" for m in measures)
        patches = [(m.get("idf_patch") or {}).get("name") for m in measures]
        assert patches == [
            "fan_avail_occupied_office",
            "premium_fan_vfd",
            "high_efficiency_chiller",
            "condensing_boiler",
            "high_performance_glazing",
        ]

    def test_electrify_set_swaps_boiler_for_awhp_surrogate(self):
        measures = expand_measure_set("school_30yr_electrify")
        assert [m["measure_id"] for m in measures] == ELECTRIFY_IDS
        awhp = next(m for m in measures if m["measure_id"] == "ECM-AWHP-SURROGATE")
        assert (awhp.get("idf_patch") or {}).get("name") == "awhp_surrogate"
        assert "conceptual_system_surrogate" in (awhp.get("flags") or [])

    def test_glazing_measure_carries_conceptual_envelope_flag(self):
        measures = expand_measure_set("school_30yr_hydronic")
        glazing = next(
            m for m in measures if m["measure_id"] == "ECM-WINDOW-HP-GLAZING"
        )
        assert "conceptual_envelope_proxy" in (glazing.get("flags") or [])

    @pytest.mark.parametrize(
        ("set_id", "measure_id"),
        [
            ("school_30yr_hydronic", "ECM-CHILLER-REPLACE-HIEFF"),
            ("school_30yr_hydronic", "ECM-CONDENSING-BOILER"),
        ],
    )
    def test_major_equipment_replacements_carry_conceptual_flags(
        self, set_id, measure_id
    ):
        measure = next(
            m for m in expand_measure_set(set_id) if m["measure_id"] == measure_id
        )
        assert any(
            flag.startswith("conceptual_") for flag in measure.get("flags") or []
        )

    def test_list_measure_sets_includes_school_sets_and_classics(self):
        ids = {s["id"] for s in list_measure_sets()}
        assert {"good", "better", "best"}.issubset(ids)
        assert {"school_30yr_hydronic", "school_30yr_electrify"}.issubset(ids)

    def test_unknown_measure_set_error_lists_available(self):
        with pytest.raises(ValueError, match="school_30yr_hydronic"):
            expand_measure_set("nope")

    def test_easy_button_cli_accepts_school_set_dynamically(self, tmp_path, capsys):
        from wattlab.easy_button import main as eb_main

        profile = {
            "project_id": "CLI-TEST",
            "display_name": "CLI test",
            "measure_set": "school_30yr_hydronic",
        }
        p = tmp_path / "profile.json"
        p.write_text(json.dumps(profile), encoding="utf-8")
        rc = eb_main(
            [
                "--building",
                str(p),
                "--dry-run",
                "--measure-set",
                "school_30yr_electrify",
            ]
        )
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["approved_measure_ids"] == ELECTRIFY_IDS

    def test_easy_button_cli_rejects_unknown_set(self, tmp_path):
        from wattlab.easy_button import main as eb_main

        with pytest.raises(SystemExit):
            eb_main(["--dry-run", "--measure-set", "not_a_set"])


# ---------------------------------------------------------------------------
# Cost scope hints + cost bases (building_ft2 vs glazing_ft2)
# ---------------------------------------------------------------------------


class TestCostScopesAndBases:
    @pytest.mark.parametrize(
        ("measure_id", "scope"),
        [
            ("ECM-AHU-SCHED-ALIGN", "rcx_tuning"),
            ("ECM-PREMIUM-FAN-VFD", "major_hvac"),
            ("ECM-CHILLER-REPLACE-HIEFF", "major_hvac"),
            ("ECM-CONDENSING-BOILER", "major_hvac"),
            ("ECM-AWHP-SURROGATE", "deep_electrification"),
            ("ECM-WINDOW-HP-GLAZING", "windows_full_replacement"),
        ],
    )
    def test_scope_for_measure_hints(self, measure_id, scope):
        assert scope_for_measure(measure_id) == scope

    def test_window_cost_uses_glazing_ft2_basis(self):
        cost = rehearsal.measure_cost_usd(
            "ECM-WINDOW-HP-GLAZING",
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_000.0,
        )
        assert cost["unit_basis"] == "glazing_ft2"
        assert cost["cost_usd"] == pytest.approx(39.7 * 5_000.0)

    def test_chiller_cost_uses_building_ft2_basis(self):
        cost = rehearsal.measure_cost_usd(
            "ECM-CHILLER-REPLACE-HIEFF",
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_000.0,
        )
        assert cost["unit_basis"] == "building_ft2"
        assert cost["cost_usd"] == pytest.approx(0.4 * 4.6 * 100_000.0)

    def test_awhp_cost_uses_deep_electrification_band(self):
        cost = rehearsal.measure_cost_usd(
            "ECM-AWHP-SURROGATE",
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_000.0,
        )
        assert cost["scope"] == "deep_electrification"
        assert cost["package_share"] is None
        # registry p50 = $32/ft2 building area (no package share)
        assert cost["cost_usd"] == pytest.approx(32.0 * 100_000.0)

    @pytest.mark.parametrize(
        "measure_set", ["school_30yr_hydronic", "school_30yr_electrify"]
    )
    def test_scenario_major_hvac_components_sum_to_one_package(self, measure_set):
        measures = expand_measure_set(measure_set)
        costs = [
            rehearsal.measure_cost_usd(
                m["measure_id"],
                floor_area_ft2=100_000.0,
                glazing_area_ft2=5_000.0,
            )
            for m in measures
        ]
        hvac = [c for c in costs if c["scope"] == "major_hvac"]
        assert all(c["scope"] != "deep_retrofit" for c in costs)
        if measure_set == "school_30yr_hydronic":
            # fan 0.2 + chiller 0.4 + boiler 0.4
            assert sum(c["package_share"] for c in hvac) == pytest.approx(1.0)
            assert sum(c["cost_usd"] for c in hvac) == pytest.approx(4.6 * 100_000.0)
        else:
            # electrify: AWHP moved to deep_electrification; remaining major_hvac = 0.6
            assert sum(c["package_share"] for c in hvac) == pytest.approx(0.6)
            deep = [c for c in costs if c["scope"] == "deep_electrification"]
            assert any(c["measure_id"] == "ECM-AWHP-SURROGATE" for c in deep)

    def test_glazing_area_estimate_geometry(self):
        # 100k ft2 / 2 floors -> 50k ft2 square footprint, 26 ft of wall height
        area = rehearsal.estimate_glazing_area_ft2(
            floor_area_ft2=100_000.0, floors=2, wwr=0.25, floor_to_floor_ft=13.0
        )
        side = (50_000.0) ** 0.5
        expected = 4 * side * 26.0 * 0.25
        assert area == pytest.approx(expected, rel=1e-6)
        assert 5_000.0 < area < 7_000.0


# ---------------------------------------------------------------------------
# Pseudo-actual bills: UtilityDataset validation + blended rates
# ---------------------------------------------------------------------------


class TestSchoolBills:
    def test_school_csvs_are_shipable_but_other_vibe20_csvs_remain_ignored(self):
        repo_root = ROOT.parent
        if not shutil.which("git"):
            pytest.skip("git not available in tip image")

        def ignored(relative_path: str) -> bool:
            completed = subprocess.run(
                ["git", "check-ignore", "--quiet", "--", relative_path],
                cwd=repo_root,
                check=False,
            )
            return completed.returncode == 0

        assert not ignored("vibe_code_apps_20/examples/school_30yr/electricity.csv")
        assert not ignored("vibe_code_apps_20/examples/school_30yr/gas.csv")
        assert ignored("vibe_code_apps_20/examples/liberty/Liberty_100_Gas_Summary.csv")

    def test_campus_files_exist(self):
        assert CAMPUS.is_file()
        assert (CAMPUS.parent / "electricity.csv").is_file()
        assert (CAMPUS.parent / "gas.csv").is_file()
        assert (CAMPUS.parent / "README.md").is_file()

    def test_campus_json_declares_synthetic_rehearsal_provenance(self):
        doc = json.loads(CAMPUS.read_text(encoding="utf-8"))
        assert doc["provenance"] == "synthetic_rehearsal"
        assert "fictional" in (doc.get("notes") or "").lower()

    def test_bills_validate_through_utility_dataset(self):
        loaded = rehearsal.load_school_bills(CAMPUS)
        assert loaded["provenance"] == "synthetic_rehearsal"
        assert loaded["floor_area_ft2"] == pytest.approx(100_000.0)
        elec = loaded["datasets"]["electricity"]
        gas = loaded["datasets"]["gas"]
        assert isinstance(elec, UtilityDataset)
        assert isinstance(gas, UtilityDataset)
        assert len(elec.bills) == 12 and len(gas.bills) == 12
        assert {b.month[:4] for b in elec.bills} == {"2025"}
        assert {b.month[:4] for b in gas.bills} == {"2025"}
        assert all(b.unit == "kwh" for b in elec.bills)
        assert all(b.unit == "therm" for b in gas.bills)
        assert all(b.demand_kw and b.demand_kw > 0 for b in elec.bills)

    def test_blended_rates_match_cost_over_usage(self):
        loaded = rehearsal.load_school_bills(CAMPUS)
        rates = rehearsal.blended_rates(loaded["datasets"])
        elec = loaded["datasets"]["electricity"]
        gas = loaded["datasets"]["gas"]
        expected_elec = sum(b.cost_usd for b in elec.bills) / sum(
            b.usage for b in elec.bills
        )
        expected_gas = sum(b.cost_usd for b in gas.bills) / sum(
            b.usage for b in gas.bills
        )
        assert rates["elec_usd_per_kwh"] == pytest.approx(expected_elec, rel=1e-3)
        assert rates["gas_usd_per_therm"] == pytest.approx(expected_gas, rel=1e-3)
        # sanity bands for a plausible Michigan school
        assert 0.08 < rates["elec_usd_per_kwh"] < 0.25
        assert 0.60 < rates["gas_usd_per_therm"] < 1.60

    def test_bills_are_seasonal_and_eui_plausible_for_k12(self):
        loaded = rehearsal.load_school_bills(CAMPUS)
        summary = rehearsal.bills_summary(
            loaded["datasets"], loaded["floor_area_ft2"]
        )
        assert len(summary["monthly_kwh"]) == 12
        gas = loaded["datasets"]["gas"]
        by_month = {b.month: b.usage for b in gas.bills}
        # winter heating must dominate summer for a Detroit school
        assert by_month["2025-01"] > 8 * by_month["2025-07"]
        # inside (or near) the EPA k12 screening band 31-65 kBtu/ft2
        assert 35.0 < summary["site_eui_kbtu_ft2"] < 65.0


# ---------------------------------------------------------------------------
# 30-year economics
# ---------------------------------------------------------------------------


class TestThirtyYearEconomics:
    def test_measure_economics_30yr_npv_manual_check(self):
        row = measure_economics(
            measure_id="X",
            implementation_cost_usd=100_000.0,
            cost_saved_usd=10_000.0,
            measure_life_years=30,
            discount_rate=0.05,
            escalation_rate=0.025,
        )
        flows = [10_000.0 * 1.025**y for y in range(30)]
        expected_npv = sum(
            f / 1.05 ** (y + 1) for y, f in enumerate(flows)
        ) - 100_000.0
        assert row["npv_usd"] == pytest.approx(expected_npv, abs=0.01)
        assert row["measure_life_years"] == 30

    def test_thirty_year_plan_rows_use_analysis_years_and_cost_bases(self):
        deltas = [
            {
                "measure_id": "ECM-WINDOW-HP-GLAZING",
                "kwh_saved_scaled": 40_000.0,
                "therms_saved_scaled": 3_000.0,
            },
            {
                "measure_id": "ECM-CHILLER-REPLACE-HIEFF",
                "kwh_saved_scaled": 90_000.0,
                "therms_saved_scaled": 0.0,
            },
        ]
        plan = rehearsal.thirty_year_plan(
            deltas,
            rates={"elec_usd_per_kwh": 0.14, "gas_usd_per_therm": 1.05},
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_000.0,
        )
        rows = {r["measure_id"]: r for r in plan["measures"]}
        assert all(
            r["measure_life_years"] == rehearsal.ANALYSIS_YEARS
            for r in plan["measures"]
        )
        assert rows["ECM-WINDOW-HP-GLAZING"]["implementation_cost_usd"] == (
            pytest.approx(39.7 * 5_000.0)
        )
        assert rows["ECM-CHILLER-REPLACE-HIEFF"]["implementation_cost_usd"] == (
            pytest.approx(0.4 * 4.6 * 100_000.0)
        )
        assert rows["ECM-WINDOW-HP-GLAZING"]["cost_basis"]["unit_basis"] == (
            "glazing_ft2"
        )
        assert plan["totals"]["implementation_cost_usd"] > 0
        assert plan["application_order"] == [
            "ECM-WINDOW-HP-GLAZING",
            "ECM-CHILLER-REPLACE-HIEFF",
        ]
        assert plan["plan_sort"] == "simple_payback_years"
        assert "application order" in plan["order_note"].lower()


# ---------------------------------------------------------------------------
# Area scaling of incremental EnergyPlus deltas
# ---------------------------------------------------------------------------


def _fake_report(measure_set: str, run_dir: str = ".artifacts/fake") -> dict:
    """Canned easy-button report: baseline + one record per set measure."""
    measures = expand_measure_set(measure_set)
    base_kwh, base_therms = 90_000.0, 5_200.0
    records = [
        {
            "run_id": "fake_baseline",
            "measure_id": None,
            "status": "COMPLETE",
            "annual": {
                "electricity_kwh_year": base_kwh,
                "natural_gas_therm_year": base_therms,
                "site_eui_kbtu_ft2_year": 80.0,
                "utility_cost_usd_year": base_kwh * 0.13 + base_therms * 1.05,
                "building_area_m2": 463.6,  # ~4,990 ft2 prototype
            },
            "monthly": [
                {
                    "month": i,
                    "electricity_kwh": base_kwh / 12,
                    "natural_gas_therm": base_therms / 12,
                }
                for i in range(1, 13)
            ],
            "quality_flags": ["uncalibrated", "conceptual_screening"],
        }
    ]
    kwh, therms = base_kwh, base_therms
    for m in measures:
        kwh *= 0.95
        therms *= 0.93
        records.append(
            {
                "run_id": f"fake_{m['measure_id']}",
                "measure_id": m["measure_id"],
                "status": "COMPLETE",
                "annual": {
                    "electricity_kwh_year": kwh,
                    "natural_gas_therm_year": therms,
                    "site_eui_kbtu_ft2_year": 70.0,
                    "utility_cost_usd_year": kwh * 0.13 + therms * 1.05,
                    "building_area_m2": 463.6,
                },
                "monthly": [],
                "quality_flags": list(m.get("flags") or []),
            }
        )
    return {
        "result_records": records,
        "savings_by_measure": savings_by_measure(records),
        "artifacts_dir": run_dir,
        "measure_set": measure_set,
        "patches": [],
    }


class TestAreaScaling:
    def test_area_scale_from_report(self):
        report = _fake_report("school_30yr_hydronic")
        scale = rehearsal.area_scale_from_report(report, 100_000.0)
        model_ft2 = 463.6 * 10.7639
        assert scale == pytest.approx(100_000.0 / model_ft2, rel=1e-6)

    def test_scaled_measure_deltas_multiply_incremental_savings(self):
        report = _fake_report("school_30yr_hydronic")
        deltas = rehearsal.scaled_measure_deltas(report, 100_000.0)
        assert [d["measure_id"] for d in deltas] == HYDRONIC_IDS
        scale = rehearsal.area_scale_from_report(report, 100_000.0)
        first = deltas[0]
        raw_kwh = 90_000.0 * 0.05
        assert first["kwh_saved"] == pytest.approx(raw_kwh, rel=1e-3)
        assert first["kwh_saved_scaled"] == pytest.approx(
            raw_kwh * scale, rel=1e-3
        )
        raw_therms = 5_200.0 * 0.07
        assert first["therms_saved_scaled"] == pytest.approx(
            raw_therms * scale, rel=1e-3
        )
        assert first["area_scale"] == pytest.approx(scale, rel=1e-6)

    def test_awhp_opposite_sign_fuel_switch_keeps_net_economics(self):
        model_area_m2 = 100_000.0 / 10.7639
        records = [
            {
                "measure_id": None,
                "status": "COMPLETE",
                "annual": {
                    "electricity_kwh_year": 100_000.0,
                    "natural_gas_therm_year": 10_000.0,
                    "utility_cost_usd_year": 24_500.0,
                    "building_area_m2": model_area_m2,
                },
            },
            {
                "measure_id": "ECM-AWHP-SURROGATE",
                "status": "COMPLETE",
                "annual": {
                    "electricity_kwh_year": 120_000.0,
                    "natural_gas_therm_year": 6_000.0,
                    "utility_cost_usd_year": 23_100.0,
                    "building_area_m2": model_area_m2,
                },
            },
        ]
        report = {
            "result_records": records,
            "savings_by_measure": savings_by_measure(records),
        }
        deltas = rehearsal.scaled_measure_deltas(report, 100_000.0)
        assert deltas == [
            {
                "measure_id": "ECM-AWHP-SURROGATE",
                "kwh_saved": -20_000.0,
                "therms_saved": 4_000.0,
                "kwh_saved_scaled": -20_000.0,
                "therms_saved_scaled": 4_000.0,
                "area_scale": 1.0,
            }
        ]

        plan = rehearsal.thirty_year_plan(
            deltas,
            rates={"elec_usd_per_kwh": 0.14, "gas_usd_per_therm": 1.05},
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_000.0,
        )
        awhp = plan["measures"][0]
        assert awhp["kwh_saved"] == -20_000.0
        assert awhp["therms_saved"] == 4_000.0
        assert awhp["annual_cost_saved_usd"] == pytest.approx(1_400.0)
        assert awhp["npv_usd"] < -100_000.0


# ---------------------------------------------------------------------------
# Dual-fuel G14
# ---------------------------------------------------------------------------


def _g14_report(monthly_kwh, monthly_therms):
    return {
        "result_records": [
            {
                "measure_id": None,
                "status": "COMPLETE",
                "annual": {"building_area_m2": 100_000.0 / 10.7639},
                "monthly": [
                    {
                        "month": month,
                        "electricity_kwh": kwh,
                        "natural_gas_therm": therms,
                    }
                    for month, (kwh, therms) in enumerate(
                        zip(monthly_kwh, monthly_therms), start=1
                    )
                ],
            }
        ]
    }


class TestDualFuelG14:
    def test_electric_pass_gas_fail_is_not_calibrated(self):
        electric = [10_000.0 + month * 100 for month in range(12)]
        gas_modeled = [1_000.0 + month * 50 for month in range(12)]
        gas_bills = [value * 2.0 for value in gas_modeled]
        result = rehearsal.baseline_g14(
            _g14_report(electric, gas_modeled),
            monthly_kwh_bills=electric,
            monthly_therm_bills=gas_bills,
            floor_area_ft2=100_000.0,
        )
        assert result["electricity"]["calibrated"] is True
        assert result["natural_gas"]["calibrated"] is False
        assert result["calibrated"] is False
        assert result["natural_gas"]["nmbe_percent"] != 0

    def test_both_fuels_pass_is_calibrated(self):
        electric = [10_000.0 + month * 100 for month in range(12)]
        gas = [1_000.0 + month * 50 for month in range(12)]
        result = rehearsal.baseline_g14(
            _g14_report(electric, gas),
            monthly_kwh_bills=electric,
            monthly_therm_bills=gas,
            floor_area_ft2=100_000.0,
        )
        assert result["calibrated"] is True
        assert result["electricity"]["calibrated"] is True
        assert result["natural_gas"]["calibrated"] is True
        assert result["errors"] == []

    def test_missing_modeled_gas_reports_per_fuel_error(self):
        electric = [10_000.0] * 12
        report = _g14_report(electric, [None] * 12)
        result = rehearsal.baseline_g14(
            report,
            monthly_kwh_bills=electric,
            monthly_therm_bills=[1_000.0] * 12,
            floor_area_ft2=100_000.0,
        )
        assert result["calibrated"] is False
        assert result["electricity"]["calibrated"] is True
        assert result["natural_gas"]["calibrated"] is False
        assert result["natural_gas"]["error"]


# ---------------------------------------------------------------------------
# Release guard
# ---------------------------------------------------------------------------


def _guard_kwargs(**overrides):
    kwargs = dict(
        scenario=RetrofitScenario(
            name="guard-clear",
            measure_ids=["ECM-AHU-SCHED-ALIGN"],
            scenario_kind="hydronic_renewal",
            analysis_years=30,
            conceptual_surrogate=False,
        ),
        g14={
            "calibrated": True,
            "electricity": {"calibrated": True},
            "natural_gas": {"calibrated": True},
        },
        result_records=[
            {"measure_id": None, "status": "COMPLETE", "quality_flags": []},
            {
                "measure_id": "ECM-AHU-SCHED-ALIGN",
                "status": "COMPLETE",
                "quality_flags": [],
            },
        ],
        weather={"sha256": "a" * 64, "source": "open-meteo-archive"},
        bills_provenance="actual",
    )
    kwargs.update(overrides)
    return kwargs


class TestReleaseGuard:
    def test_all_clear_publishes(self):
        verdict = rehearsal.release_guard(**_guard_kwargs())
        assert verdict["verdict"] == "PUBLISH"
        assert verdict["reasons"] == []

    def test_g14_failure_forces_investigate(self):
        verdict = rehearsal.release_guard(
            **_guard_kwargs(
                g14={
                    "calibrated": False,
                    "electricity": {"calibrated": True},
                    "natural_gas": {"calibrated": False},
                }
            )
        )
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("g14" in r.lower() for r in verdict["reasons"])

    def test_missing_g14_forces_investigate(self):
        verdict = rehearsal.release_guard(**_guard_kwargs(g14=None))
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("g14" in r.lower() for r in verdict["reasons"])

    def test_conceptual_surrogate_flag_forces_investigate(self):
        records = [
            {"measure_id": None, "status": "COMPLETE", "quality_flags": []},
            {
                "measure_id": "ECM-AWHP-SURROGATE",
                "status": "COMPLETE",
                "quality_flags": ["conceptual_system_surrogate"],
            },
        ]
        verdict = rehearsal.release_guard(
            **_guard_kwargs(result_records=records)
        )
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("conceptual" in r.lower() for r in verdict["reasons"])

    def test_scenario_conceptual_surrogate_forces_investigate_without_result_flags(self):
        scenario = RetrofitScenario(
            name="explicit-surrogate",
            measure_ids=["ECM-AWHP-SURROGATE"],
            scenario_kind="electrification",
            analysis_years=30,
            conceptual_surrogate=True,
        )
        verdict = rehearsal.release_guard(
            **_guard_kwargs(scenario=scenario)
        )
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("scenario" in r.lower() and "conceptual" in r.lower() for r in verdict["reasons"])

    def test_generic_conceptual_screening_flag_does_not_trip_surrogate_check(self):
        # every uncalibrated baseline carries conceptual_screening; only
        # surrogate/proxy patches should trip the guard
        records = [
            {
                "measure_id": None,
                "status": "COMPLETE",
                "quality_flags": ["uncalibrated", "conceptual_screening"],
            },
        ]
        verdict = rehearsal.release_guard(
            **_guard_kwargs(result_records=records)
        )
        assert verdict["verdict"] == "PUBLISH"

    def test_incomplete_simulation_forces_investigate(self):
        records = [
            {"measure_id": None, "status": "COMPLETE", "quality_flags": []},
            {
                "measure_id": "ECM-AHU-SCHED-ALIGN",
                "status": "MODEL_RUN_FAILED",
                "quality_flags": [],
            },
        ]
        verdict = rehearsal.release_guard(
            **_guard_kwargs(result_records=records)
        )
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("simulation" in r.lower() for r in verdict["reasons"])

    def test_no_simulation_records_forces_investigate(self):
        verdict = rehearsal.release_guard(**_guard_kwargs(result_records=[]))
        assert verdict["verdict"] == "INVESTIGATE"

    def test_missing_weather_provenance_forces_investigate(self):
        verdict = rehearsal.release_guard(**_guard_kwargs(weather={}))
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("weather" in r.lower() for r in verdict["reasons"])

    def test_missing_bills_provenance_forces_investigate(self):
        verdict = rehearsal.release_guard(**_guard_kwargs(bills_provenance=None))
        assert verdict["verdict"] == "INVESTIGATE"
        assert any("bill" in r.lower() for r in verdict["reasons"])

    def test_unknown_bills_provenance_forces_investigate(self):
        verdict = rehearsal.release_guard(
            **_guard_kwargs(bills_provenance="somebody_said_so")
        )
        assert verdict["verdict"] == "INVESTIGATE"


# ---------------------------------------------------------------------------
# Profile resolution + actual-year weather suitability
# ---------------------------------------------------------------------------


class TestSchoolProfile:
    def test_amy_note_text_alone_is_not_trusted_provenance(self):
        wx = weather_suitability(
            epw_note="Actual Meteorological Year EPW built from observed weather."
        )
        assert wx["mode"] != ACTUAL_YEAR_CALIBRATION

    def test_amy_requires_explicit_trusted_source(self):
        wx = weather_suitability(
            source="amy",
            epw_note=(
                "Actual Meteorological Year EPW built from Open-Meteo archive "
                "hourly weather for Detroit, MI, calendar 2025."
            ),
        )
        assert wx["mode"] == ACTUAL_YEAR_CALIBRATION

    def test_substitute_hint_wins_over_amy_note_substring(self):
        wx = weather_suitability(
            epw_note="Chicago TMY3 until AMY EPW arrives",
            city_id="detroit",
        )
        assert wx["mode"] == SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY

    def test_rehearsal_explicit_amy_source_remains_actual_year(self):
        wx = weather_suitability(
            source="amy",
            epw_note="Actual Meteorological Year EPW built from Open-Meteo.",
            city_id="detroit",
        )
        assert wx["mode"] == ACTUAL_YEAR_CALIBRATION

    def test_build_school_profile_geometry_and_weather(self, tmp_path):
        epw = tmp_path / "detroit_2025.epw"
        epw.write_text("LOCATION,fake\n", encoding="utf-8")
        note = "Actual Meteorological Year EPW built from Open-Meteo (rehearsal)."
        profile = rehearsal.build_school_profile(
            "school_30yr_hydronic",
            epw_path=epw,
            epw_note=note,
            rates={"elec_usd_per_kwh": 0.1417, "gas_usd_per_therm": 1.0537},
        )
        assert profile["building_type"] == "school"
        assert profile["conditioned_floor_area_ft2"] == pytest.approx(100_000.0)
        assert profile["number_of_floors"] == 2
        assert profile["wwr"] == pytest.approx(0.25)
        assert profile["energyplus"]["epw"] == str(epw)
        assert profile["energyplus"]["epw_note"] == note
        assert profile["utility"]["elec_usd_per_kwh"] == pytest.approx(0.1417)
        wx = weather_suitability(
            source="amy",
            epw_path=profile["energyplus"]["epw"],
            epw_note=profile["energyplus"]["epw_note"],
            city_id="detroit",
        )
        assert wx["mode"] == ACTUAL_YEAR_CALIBRATION

    def test_scenario_contracts_are_valid_and_explicit(self):
        hyd = rehearsal.scenario_contract("school_30yr_hydronic")
        ele = rehearsal.scenario_contract("school_30yr_electrify")
        assert isinstance(hyd, RetrofitScenario)
        assert hyd.scenario_kind == "hydronic_renewal"
        assert ele.scenario_kind == "electrification"
        assert hyd.analysis_years == 30 and ele.analysis_years == 30
        assert hyd.measure_ids == HYDRONIC_IDS
        assert ele.measure_ids == ELECTRIFY_IDS
        # both sets include explicit conceptual surrogates (glazing proxy /
        # AWHP-as-electric-boiler), so this must be declared
        assert hyd.conceptual_surrogate is True
        assert ele.conceptual_surrogate is True


# ---------------------------------------------------------------------------
# Mocked end-to-end orchestration (no network, no Docker)
# ---------------------------------------------------------------------------


def _hourly_times(start: date, hours: int) -> list[str]:
    t0 = datetime(start.year, start.month, start.day)
    return [
        (t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)
    ]


def _detroit_year_payload() -> dict:
    hours = 8760
    times = _hourly_times(date(2025, 1, 1), hours)
    hourly: dict[str, list] = {"time": times}
    hourly["temperature_2m"] = [30.0 + 0.001 * i for i in range(hours)]
    hourly["dew_point_2m"] = [20.0 for _ in range(hours)]
    hourly["relative_humidity_2m"] = [50.0 for _ in range(hours)]
    hourly["surface_pressure"] = [990.0 for _ in range(hours)]
    hourly["shortwave_radiation"] = [100.0 for _ in range(hours)]
    hourly["direct_normal_irradiance"] = [200.0 for _ in range(hours)]
    hourly["diffuse_radiation"] = [50.0 for _ in range(hours)]
    hourly["wind_speed_10m"] = [8.0 for _ in range(hours)]
    hourly["wind_direction_10m"] = [270.0 for _ in range(hours)]
    return {
        "latitude": rehearsal.DETROIT_LAT,
        "longitude": rehearsal.DETROIT_LON,
        "timezone": "GMT",
        "hourly": hourly,
    }


class TestMockedOrchestration:
    @pytest.mark.parametrize(
        ("execution_outcome", "expected_rc"),
        [("SIMULATION_COMPLETE", 0), ("SIMULATION_FAILED", 1)],
    )
    def test_main_exit_code_tracks_execution_not_review_status(
        self, monkeypatch, execution_outcome, expected_rc
    ):
        monkeypatch.setattr(
            rehearsal,
            "run_rehearsal",
            lambda **kwargs: {
                "execution_outcome": execution_outcome,
                "release": {"verdict": "INVESTIGATE"},
            },
        )
        assert rehearsal.main([]) == expected_rc

    def test_run_rehearsal_end_to_end_mocked(self, tmp_path):
        payload_bytes = json.dumps(_detroit_year_payload()).encode("utf-8")
        urls: list[str] = []

        def opener(url: str) -> bytes:
            urls.append(url)
            return payload_bytes

        calls: list[str] = []

        def runner(*, profile=None, measure_set=None, **kwargs):
            calls.append(measure_set)
            assert profile is not None
            assert profile["measure_set"] == measure_set
            return _fake_report(measure_set, run_dir=str(tmp_path / measure_set))

        out_path = tmp_path / "school_30yr_rehearsal.json"
        result = rehearsal.run_rehearsal(
            cache_dir=tmp_path / "cache",
            out_path=out_path,
            opener=opener,
            easy_button_runner=runner,
        )

        # network hit exactly once (cache handles the rest); Docker never used
        assert len(urls) == 1
        assert calls == ["school_30yr_hydronic", "school_30yr_electrify"]

        assert out_path.is_file()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data == result or data.keys() == result.keys()

        # inputs / provenance
        assert data["inputs"]["provenance"]["bills"] == "synthetic_rehearsal"
        assert data["inputs"]["building"]["floor_area_ft2"] == 100_000.0
        assert data["inputs"]["analysis_years"] == 30

        # weather SHA + cache + suitability + annual EPW
        wx = data["weather"]
        assert wx["sha256"] == hashlib.sha256(payload_bytes).hexdigest()
        assert Path(wx["cached_path"]).is_file()
        assert wx["meta"]["rows"] == 8760
        assert wx["suitability"]["mode"] == ACTUAL_YEAR_CALIBRATION
        assert Path(wx["epw"]["epw"]).is_file()
        assert wx["epw"]["rows"] == 8760
        assert wx["epw"]["time_basis"] == "local_standard"
        assert wx["epw"]["tz_hours"] == -5.0
        assert wx["epw"]["start_local_standard"] == "2025-01-01 00:00:00"
        assert wx["epw"]["end_local_standard"] == "2025-12-31 23:00:00"
        assert "start_utc" not in wx["epw"]
        assert "end_utc" not in wx["epw"]

        # bills summary
        bills = data["bills"]
        assert bills["annual_kwh"] > 500_000
        assert bills["annual_therms"] > 10_000
        assert len(bills["monthly_kwh"]) == 12

        # scenarios: plans, gates, g14, release
        assert set(data["scenarios"]) == {
            "school_30yr_hydronic",
            "school_30yr_electrify",
        }
        for set_id, block in data["scenarios"].items():
            plan = block["capital_plan"]
            assert plan["totals"]["implementation_cost_usd"] > 0
            assert all(
                r["measure_life_years"] == 30 for r in plan["measures"]
            )
            assert block["gate"]["verdict"] in {"PUBLISH", "INVESTIGATE"}
            assert block["g14"] is not None
            # conceptual glazing / AWHP surrogates must force INVESTIGATE
            assert block["release"]["verdict"] == "INVESTIGATE"
            assert any(
                "conceptual" in r.lower() for r in block["release"]["reasons"]
            )
            assert block["artifacts_dir"]

        assert data["release"]["verdict"] == "INVESTIGATE"
        assert data["execution_outcome"] == "SIMULATION_COMPLETE"
        assert sum(
            len(block["result_records"]) for block in data["scenarios"].values()
        ) == 12
        comparison = data["comparison"]
        assert comparison["scenario_order"] == [
            "school_30yr_hydronic",
            "school_30yr_electrify",
        ]
        assert len(comparison["scenarios"]) == 2
        for row in comparison["scenarios"]:
            assert set(row) >= {
                "scenario",
                "annual_kwh_saved",
                "annual_therms_saved",
                "annual_cost_saved_usd",
                "implementation_cost_usd",
                "npv_usd",
                "release_verdict",
            }

    def test_electrify_plan_prices_awhp_as_deep_electrification(self, tmp_path):
        report = _fake_report("school_30yr_electrify")
        deltas = rehearsal.scaled_measure_deltas(report, 100_000.0)
        plan = rehearsal.thirty_year_plan(
            deltas,
            rates={"elec_usd_per_kwh": 0.14, "gas_usd_per_therm": 1.05},
            floor_area_ft2=100_000.0,
            glazing_area_ft2=5_813.8,
        )
        rows = {r["measure_id"]: r for r in plan["measures"]}
        assert rows["ECM-AWHP-SURROGATE"]["implementation_cost_usd"] == (
            pytest.approx(32.0 * 100_000.0)
        )
        assert rows["ECM-AWHP-SURROGATE"]["cost_basis"]["scope"] == "deep_electrification"


# ---------------------------------------------------------------------------
# Regression: EPW rows must be local standard time, not UTC (live-run bug)
# ---------------------------------------------------------------------------


class TestEpwLocalStandardTimeRegression:
    """Found live: UTC-stamped EPW rows + a longitude-derived header timezone
    (-6.0) misaligned solar radiation by ~5-6 h; EnergyPlus 26.1 emitted 884
    severe 'Temperature (high/low) out of bounds' errors per annual run. Rows
    must be shifted to local standard time (circular year wrap) and the
    LOCATION header timezone must match.
    """

    def _utc_year(self) -> "pd.DataFrame":
        import pandas as pd

        idx = pd.date_range("2025-01-01", periods=8760, freq="1h", tz="UTC")
        return pd.DataFrame({"dry_bulb_f": [float(i % 1000) / 100.0 + 30.0 for i in range(8760)]}, index=idx)

    def test_utc_frame_to_local_standard_shifts_and_wraps(self):
        import pandas as pd

        from wattlab.weather.epw import utc_frame_to_local_standard

        df = self._utc_year()
        local = utc_frame_to_local_standard(df, tz_hours=-5)
        assert len(local) == 8760
        assert local.index[0] == pd.Timestamp("2025-01-01T00:00")
        assert local.index[-1] == pd.Timestamp("2025-12-31T23:00")
        deltas = local.index.to_series().diff().dropna().unique()
        assert list(deltas) == [pd.Timedelta(hours=1)]
        # local Jan 1 00:00 EST == UTC Jan 1 05:00 (row 5)
        assert local["dry_bulb_f"].iloc[0] == df["dry_bulb_f"].iloc[5]
        # wrapped tail: local Dec 31 19:00-23:00 reuse UTC Jan 1 00:00-04:00
        assert list(local["dry_bulb_f"].iloc[-5:]) == list(
            df["dry_bulb_f"].iloc[:5]
        )

    def test_utc_frame_to_local_standard_requires_full_year(self):
        import pandas as pd

        from wattlab.weather.epw import utc_frame_to_local_standard

        idx = pd.date_range("2025-01-01", periods=48, freq="1h", tz="UTC")
        df = pd.DataFrame({"dry_bulb_f": 30.0}, index=idx)
        with pytest.raises(ValueError, match="(?i)calendar year"):
            utc_frame_to_local_standard(df, tz_hours=-5)

    def test_build_amy_epw_honors_tz_hours_override(self, tmp_path):
        import pandas as pd

        from wattlab.weather.epw import build_amy_epw

        idx = pd.date_range("2025-01-01", periods=8760, freq="1h")
        df = pd.DataFrame(
            {
                "dry_bulb_f": 30.0,
                "dew_point_f": 20.0,
                "relative_humidity_pct": 50.0,
                "surface_pressure_hpa": 990.0,
                "shortwave_radiation_wm2": 100.0,
                "direct_normal_irradiance_wm2": 200.0,
                "diffuse_radiation_wm2": 50.0,
                "wind_speed_mph": 8.0,
                "wind_direction_deg": 270.0,
            },
            index=idx,
        )
        out = tmp_path / "tz.epw"
        build_amy_epw(
            df,
            out,
            lat=42.33,
            lon=-83.05,
            tz_hours=-5.0,
            coverage_mode="annual",
        )
        location = out.read_text(encoding="utf-8").splitlines()[0].split(",")
        assert float(location[8]) == -5.0

    def test_build_school_epw_writes_local_standard_header(self, tmp_path):
        import pandas as pd

        idx = pd.date_range("2025-01-01", periods=8760, freq="1h", tz="UTC")
        df = pd.DataFrame(
            {
                "dry_bulb_f": [30.0 + (i % 24) for i in range(8760)],
                "dew_point_f": 20.0,
                "relative_humidity_pct": 50.0,
                "surface_pressure_hpa": 990.0,
                "shortwave_radiation_wm2": 100.0,
                "direct_normal_irradiance_wm2": 200.0,
                "diffuse_radiation_wm2": 50.0,
                "wind_speed_mph": 8.0,
                "wind_direction_deg": 270.0,
            },
            index=idx,
        )
        meta = WeatherDatasetMeta(
            source="open-meteo-archive",
            latitude=rehearsal.DETROIT_LAT,
            longitude=rehearsal.DETROIT_LON,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            variables=sorted(EPW_REQUIRED_VARIABLES),
            rows=8760,
            sha256="b" * 64,
        )
        out = tmp_path / "school.epw"
        epw_meta = rehearsal.build_school_epw(df, meta, out)
        assert epw_meta["rows"] == 8760
        assert epw_meta["time_basis"] == "local_standard"
        assert epw_meta["tz_hours"] == -5.0
        assert epw_meta["start_local_standard"] == "2025-01-01 00:00:00"
        assert epw_meta["end_local_standard"] == "2025-12-31 23:00:00"
        assert "start_utc" not in epw_meta
        assert "end_utc" not in epw_meta
        location = out.read_text(encoding="utf-8").splitlines()[0].split(",")
        assert float(location[8]) == rehearsal.DETROIT_TZ_HOURS == -5.0


# ---------------------------------------------------------------------------
# Live integration (opt-in): real Open-Meteo download + Docker EnergyPlus
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("RUN_SCHOOL_30YR_LIVE"),
    reason="live Open-Meteo + Docker rehearsal is opt-in (RUN_SCHOOL_30YR_LIVE=1)",
)
def test_live_school_30yr_rehearsal(tmp_path):
    from wattlab.energyplus.docker import docker_info_ok, image_present

    if not docker_info_ok():
        pytest.skip("Docker not available")
    if not image_present():
        pytest.skip("energyplus-mcp-dev image missing")

    out_path = tmp_path / "live_rehearsal.json"
    result = rehearsal.run_rehearsal(out_path=out_path)
    assert out_path.is_file()
    assert result["weather"]["suitability"]["mode"] == ACTUAL_YEAR_CALIBRATION
    records = [
        record
        for block in result["scenarios"].values()
        for record in block["result_records"]
    ]
    assert len(records) == 12
    assert all(record["status"] == "COMPLETE" for record in records)
    assert {
        block["release"]["verdict"] for block in result["scenarios"].values()
    } == {"INVESTIGATE"}

    err_files = [
        err
        for block in result["scenarios"].values()
        for err in Path(block["artifacts_dir"]).glob("sim_*/eplusout.err")
    ]
    assert len(err_files) == 12
    severe_or_fatal = re.compile(r"\*\*\s+(?:Severe|Fatal)\s+\*\*", re.IGNORECASE)
    offenders = {
        str(path): severe_or_fatal.findall(path.read_text(encoding="utf-8"))
        for path in err_files
        if severe_or_fatal.search(path.read_text(encoding="utf-8"))
    }
    assert offenders == {}
