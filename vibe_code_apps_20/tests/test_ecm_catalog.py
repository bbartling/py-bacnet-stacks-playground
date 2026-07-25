"""Validation and interaction tests for the canonical ECM registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from wattlab.ecm import (
    PRODUCTION_STATUSES,
    detect_incompatibilities,
    get_ecm,
    list_ecms,
    load_catalog,
    resolve_package,
)


PRODUCTION_MEASURES = {
    "ECM-AHU-SCHED-ALIGN": ("schedule_reduction", "fan_avail_occupied_office"),
    "ECM-GL36-AIRSIDE": ("fan_affinity", "gl36_airside_proxy"),
    "ECM-CHILLER-LOCKOUT": ("economizer_proxy", "chiller_lockout"),
    "ECM-SAT-RESET": ("temperature_reset_bins", "sat_reset"),
    "ECM-PREMIUM-FAN-VFD": ("fan_affinity", "premium_fan_vfd"),
    "ECM-CHILLER-REPLACE-HIEFF": (
        "kw_per_ton_improvement",
        "high_efficiency_chiller",
    ),
    "ECM-CONDENSING-BOILER": ("boiler_efficiency_improvement", "condensing_boiler"),
    "ECM-AWHP-SURROGATE": ("heat_pump_electrification", "awhp_surrogate"),
    "ECM-DOAS-HP": ("heat_pump_electrification", "awhp_surrogate"),
    "ECM-WINDOW-HP-GLAZING": (None, "high_performance_glazing"),
}


def test_catalog_has_unique_complete_entries_across_required_categories() -> None:
    catalog = load_catalog()
    entries = catalog.list()
    ids = [entry.ecm_id for entry in entries]
    assert len(entries) >= 30
    assert len(ids) == len(set(ids))
    assert {
        "scheduling",
        "oa_ventilation",
        "airside_vav",
        "g36",
        "pneumatic_to_ddc",
        "heating_plant",
        "cooling_plant",
        "geothermal",
        "humidity",
        "sensors_rcx",
    } <= {entry.category for entry in entries}


def test_working_measures_use_real_production_mappings() -> None:
    for ecm_id, (calculator, patch) in PRODUCTION_MEASURES.items():
        entry = get_ecm(ecm_id)
        assert entry.status in PRODUCTION_STATUSES
        assert entry.proxy_calculator == calculator
        assert entry.energyplus_patch == patch


def test_package_resolution_expands_dependencies_without_duplicates() -> None:
    full_g36 = resolve_package("full-g36-conceptual")
    assert "ECM-GL36-AIRSIDE" in full_g36
    assert "ECM-SAT-RESET" in full_g36
    assert "ECM-AHU-SCHED-ALIGN" in full_g36
    assert len(full_g36) == len(set(full_g36))

    pneumatic = resolve_package("pneumatic-to-ddc")
    assert "ECM-PNEU-DDC-CONVERT" in pneumatic
    assert "ECM-SENSOR-CRITICAL-REFRESH" in pneumatic

    esco = resolve_package("esco-top15")
    assert "ECM-CONDENSING-BOILER" in esco
    assert "ECM-ADVANCED-RTU" in esco
    assert "ECM-AHU-SCHED-ALIGN" in esco
    assert "ECM-OCC-STANDBY-DCV" in esco
    assert "ECM-DCV-CO2" not in esco  # standalone DCV superseded to avoid double-count
    assert "ECM-SENSOR-CRITICAL-REFRESH" in esco
    assert len(esco) == len(set(esco))

    erv = resolve_package("energy-recovery")
    assert erv == ["ECM-ERV", "ECM-TOILET-EXH-ERV"]

    doas = resolve_package("deep-doas-heat-pump")
    assert "ECM-DOAS-HP" in doas
    assert "ECM-ERV" in doas  # dependency
    assert "ECM-AHU-SCHED-ALIGN" in resolve_package("partial-g36")  # prior packages intact

    with pytest.raises(KeyError, match="Unknown ECM package"):
        resolve_package("not-a-package")


def test_occ_standby_dcv_is_a_production_proxy_oa_measure() -> None:
    measure = get_ecm("ECM-OCC-STANDBY-DCV")

    assert measure.category == "oa_ventilation"
    assert measure.implementation_complexity == "medium"
    assert measure.status == "PRODUCTION_PROXY_ONLY"
    assert measure.energyplus_patch is None
    assert measure.dependencies == ["ECM-SENSOR-CRITICAL-REFRESH"]
    assert "ECM-DCV-CO2" in measure.incompatibilities

    issues = detect_incompatibilities(["ECM-OCC-STANDBY-DCV", "ECM-DCV-CO2"])
    assert len(issues) == 1
    assert set(issues[0].ecm_ids) == {"ECM-OCC-STANDBY-DCV", "ECM-DCV-CO2"}


def test_incompatibility_detection_is_symmetric_and_fail_closed() -> None:
    issues = detect_incompatibilities(
        ["ECM-BOILER-TUNE", "ECM-CONDENSING-BOILER"]
    )
    assert len(issues) == 1
    assert set(issues[0].ecm_ids) == {
        "ECM-BOILER-TUNE",
        "ECM-CONDENSING-BOILER",
    }
    with pytest.raises(KeyError, match="Unknown ECM"):
        detect_incompatibilities(["ECM-DOES-NOT-EXIST"])


def test_catalog_rejects_duplicate_ids_and_extra_fields(tmp_path: Path) -> None:
    valid = get_ecm("ECM-AHU-SCHED-ALIGN").model_dump(mode="json")
    duplicate_path = tmp_path / "duplicate.yaml"
    duplicate_path.write_text(
        yaml.safe_dump({"ecms": [valid, valid]}, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate ECM id"):
        load_catalog(duplicate_path)

    invalid = dict(valid)
    invalid["unexpected"] = True
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(
        yaml.safe_dump({"ecms": [invalid]}, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_catalog(invalid_path)


def test_list_filter_and_unknown_lookup() -> None:
    assert list_ecms(category="humidity")
    assert all(entry.category == "humidity" for entry in list_ecms(category="humidity"))
    with pytest.raises(KeyError, match="Unknown ECM"):
        get_ecm("ECM-DOES-NOT-EXIST")
