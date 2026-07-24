"""Dashboard freeze — prevent Plots/RCx/UI features from being vibe-coded away."""

from __future__ import annotations

import importlib
from pathlib import Path

from app import charts, dashboard_contract
from app.rcx_plots import PRESETS, REQUIRED_RCX_PRESET_IDS, preset_by_id


def test_required_rcx_presets_present():
    ids = {p.id for p in PRESETS}
    missing = sorted(REQUIRED_RCX_PRESET_IDS - ids)
    assert not missing, f"Required RCx presets missing from PRESETS: {missing}"


def test_full_existing_catalog_is_frozen():
    """Every current PRESET id is in the freeze set (deleting one fails this test)."""
    ids = {p.id for p in PRESETS}
    # Allow adding new experimental presets later, but never silently drop frozen ones.
    assert REQUIRED_RCX_PRESET_IDS <= ids
    # Today's catalog should not shrink below the freeze list size.
    assert len(REQUIRED_RCX_PRESET_IDS) >= 12


def test_reset_scatter_and_static_box_contract():
    """Plant leave-temp scatters + duct static box + AHU SAT vs OAT must stay wired."""
    hw = preset_by_id("hw_reset_scatter")
    chw = preset_by_id("chw_reset_scatter")
    cw = preset_by_id("cw_reset_scatter")
    sat = preset_by_id("ahu_sat_reset_scatter")
    box = preset_by_id("duct_static_box")

    assert hw is not None and hw.chart == "scatter_oat" and hw.role == "hot-water-supply-temp"
    assert "BOILER" in hw.equipment_types
    assert chw is not None and chw.chart == "scatter_oat" and chw.role == "chilled-water-supply-temp"
    assert set(chw.equipment_types) & {"CHW_PLANT", "CHILLER"}
    assert cw is not None and cw.chart == "scatter_oat" and cw.role == "condenser-water-supply-temp"
    assert "COOLING_TOWER" in cw.equipment_types
    assert getattr(cw, "dry_bulb_ref", False) is True
    assert sat is not None and sat.chart == "scatter_oat" and sat.role == "discharge-air-temp"
    assert box is not None and box.chart == "box" and box.role == "duct-static-pressure" and box.filter_fan_on
    rank = preset_by_id("zone_comfort_rank")
    assert rank is not None and rank.chart == "ranking" and rank.role == "zone-air-temp"
    elec = preset_by_id("meter_elec_cdd")
    assert elec is not None and elec.chart == "metering" and elec.role == "elec-power"
    gas = preset_by_id("meter_gas_hdd")
    assert gas is not None and gas.chart == "metering" and gas.role == "gas-flow"


def test_duct_static_ts_and_plant_temp_ts_presets_wired():
    """New timeseries presets: duct static + SP overlay, CHW/CW supply+return+ΔT."""
    ds = preset_by_id("duct_static_ts")
    assert ds is not None and ds.chart == "timeseries" and ds.role == "duct-static-pressure"
    assert ds.overlay_role == "duct-static-pressure-sp"
    assert ds.family == "AHU / air" and "AHU" in ds.equipment_types

    chw = preset_by_id("chw_temps_ts")
    assert chw is not None and chw.chart == "timeseries"
    assert chw.role == "chilled-water-supply-temp"
    assert chw.pair_return_role == "chilled-water-return-temp"
    assert chw.family == "Chiller / CHW / tower"
    assert set(chw.equipment_types) & {"CHW_PLANT", "CHILLER"}

    cw = preset_by_id("cw_temps_ts")
    assert cw is not None and cw.chart == "timeseries"
    assert cw.role == "condenser-water-supply-temp"
    assert cw.pair_return_role == "condenser-water-return-temp"
    assert cw.family == "Chiller / CHW / tower"
    assert "COOLING_TOWER" in cw.equipment_types

    # Contract: frozen ids include the new presets
    assert {"duct_static_ts", "chw_temps_ts", "cw_temps_ts"} <= REQUIRED_RCX_PRESET_IDS


def test_supporting_overlay_presets_wired():
    for pid, role, chart in (
        ("zone_temps", "zone-air-temp", "timeseries"),
        ("ahu_dats", "discharge-air-temp", "timeseries"),
        ("ahu_mats", "mixed-air-temp", "timeseries"),
        ("ahu_rats", "return-air-temp", "timeseries"),
        ("ahu_dampers", "outside-air-damper", "timeseries"),
        ("vav_flows", "zone-airflow", "timeseries"),
        ("fan_speeds", "fan-cmd", "timeseries"),
    ):
        p = preset_by_id(pid)
        assert p is not None, pid
        assert p.role == role and p.chart == chart, pid


def test_rcx_families_partition_presets():
    """AHU family must not include plant/meter presets (UX mix-up)."""
    from app.rcx_plots import RCX_FAMILY_ORDER, presets_for_family

    assert RCX_FAMILY_ORDER == (
        "Zones / VAV",
        "AHU / air",
        "Boiler / HW",
        "Chiller / CHW / tower",
        "Metering",
    )
    ahu_ids = {p.id for p in presets_for_family("AHU / air")}
    assert "hw_reset_scatter" not in ahu_ids
    assert "chw_reset_scatter" not in ahu_ids
    assert "cw_reset_scatter" not in ahu_ids
    assert "meter_elec_cdd" not in ahu_ids
    assert "ahu_sat_reset_scatter" in ahu_ids
    assert "duct_static_box" in ahu_ids
    assert {p.id for p in presets_for_family("Boiler / HW")} == {"hw_reset_scatter"}
    assert "chw_reset_scatter" in {p.id for p in presets_for_family("Chiller / CHW / tower")}
    # Every preset belongs to exactly one family in the order list
    from app.rcx_plots import PRESETS

    for p in PRESETS:
        assert p.family in RCX_FAMILY_ORDER, p.id
    assert sum(len(presets_for_family(f)) for f in RCX_FAMILY_ORDER) == len(PRESETS)


def test_required_chart_apis_exist():
    for name in dashboard_contract.REQUIRED_CHART_APIS:
        assert callable(getattr(charts, name, None)), f"charts.{name} missing"


def test_required_ui_entrypoints_importable():
    for spec in dashboard_contract.REQUIRED_UI_ENTRYPOINTS:
        mod_name, attr = spec.split(":", 1)
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, attr), f"{spec} missing"


def test_streamlit_main_sections_present():
    src = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    for section in dashboard_contract.REQUIRED_MAIN_SECTIONS:
        assert f'"{section}"' in src or f"'{section}'" in src, f"section missing: {section}"
        assert f'section == "{section}"' in src or f"section == '{section}'" in src, (
            f"no branch for section: {section}"
        )
    assert "Energy Model" not in dashboard_contract.REQUIRED_MAIN_SECTIONS
    assert "Export" in dashboard_contract.REQUIRED_MAIN_SECTIONS
    assert "FDD Plots" in dashboard_contract.REQUIRED_MAIN_SECTIONS
    assert "Plots" not in dashboard_contract.REQUIRED_MAIN_SECTIONS
    assert "Data Model" in dashboard_contract.REQUIRED_MAIN_SECTIONS
    assert "load_generic_rcx_report" in " ".join(dashboard_contract.REQUIRED_UI_ENTRYPOINTS)
    assert "build_rule_card" in " ".join(dashboard_contract.REQUIRED_UI_ENTRYPOINTS)
    assert "render_engineering_findings_panel" in " ".join(dashboard_contract.REQUIRED_UI_ENTRYPOINTS)
    assert "render_overview_rcx_download" not in " ".join(dashboard_contract.REQUIRED_UI_ENTRYPOINTS)
    assert "render_energy_model_tab" not in " ".join(dashboard_contract.REQUIRED_UI_ENTRYPOINTS)
    assert "Economizer family" in src or "ECON-1" in src
    assert "render_engineering_findings_panel" in src
    assert "Download FDD DOCX" not in src
    assert "render_central_template_pack_section" not in src
    rcx_ui = (Path(__file__).resolve().parents[1] / "app" / "ui_rcx_tab.py").read_text(encoding="utf-8")
    assert "render_rcx_family_downloads" not in rcx_ui
    assert "PLACE PLOT HERE" in src or "build_rule_card" in src
    assert "rule validation cards" in src or "Filter cards" in src or "catalog parity" in src
    # Must not be the sole one-at-a-time selectbox UX without a card catalog
    assert "Filter cards" in src
    assert "Chart rule" in src or "Plot focus" in src
    assert "Download session_config.json" in src
    assert "Download role_map.json" in src
    assert "Rule facts" in src or "catalog_facts" in src
