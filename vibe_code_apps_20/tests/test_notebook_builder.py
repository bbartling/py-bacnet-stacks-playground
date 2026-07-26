"""Engineering notebook builder / prefill / validate / preview (BUG-030–050)."""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from wattlab.notebooks.builder import (
    FORMULA_ESCO_KWH,
    agent_build_notebook,
    build_and_save_notebook,
    prefill_notebook_inputs,
    preview_sheet_rows,
    read_notebook_inputs,
    resolve_building_label,
    show_formulas,
    summarize_notebook,
    sync_notebook_from_twin,
    validate_notebook,
)
from wattlab.notebooks.packages import INPUT_NAMED_RANGES, REQUIRED_SHEETS, list_notebook_packages


def test_list_notebook_packages_ladder():
    pkgs = list_notebook_packages()
    ids = [p.id for p in pkgs]
    assert ids == [
        "controls_first",
        "schedules_economizer",
        "plant_optimization",
        "esco_top15",
        "deep_retrofit",
    ]
    assert [p.rank for p in pkgs] == [1, 2, 3, 4, 5]


def test_resolve_building_label_display_name():
    assert resolve_building_label({"display_name": "Liberty Building 100"}) == "Liberty Building 100"
    assert resolve_building_label({"project_id": "LIB-100"}) == "LIB-100"
    assert resolve_building_label({}) == "BUILDING"


def test_cover_uses_display_name_bug047(tmp_path: Path):
    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={
            "display_name": "Liberty Building 100 — Detroit",
            "conditioned_floor_area_ft2": 140_000,
        },
    )
    wb = openpyxl.load_workbook(written["xlsx"], data_only=False)
    labels = {
        str(wb["Cover"][f"A{r}"].value): wb["Cover"][f"B{r}"].value
        for r in range(4, 20)
        if wb["Cover"][f"A{r}"].value
    }
    assert labels.get("Building") == "Liberty Building 100 — Detroit"
    assert labels.get("Building") != "BUILDING"


def test_build_validate_named_ranges_and_roi_formulas(tmp_path: Path):
    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"conditioned_floor_area_ft2": 140_000, "utility": {"elec_usd_per_kwh": 0.14}},
        report={},
    )
    xlsx = written["xlsx"]
    v = validate_notebook(xlsx)
    assert v["ok"] is True
    assert set(REQUIRED_SHEETS) <= set(v["sheets"])
    assert any("EPlus_Results empty" in w for w in v["warnings"])

    wb = openpyxl.load_workbook(xlsx, data_only=False)
    defined = set(wb.defined_names.keys())
    for n in INPUT_NAMED_RANGES:
        assert n in defined
    assert str(wb["ROI_Capital"]["B2"].value).startswith("=H")
    assert "inp_usd_per_ft2" in str(wb["ROI_Capital"]["H2"].value)
    assert str(wb["ROI_Capital"]["G2"].value).startswith("=IF")
    assert isinstance(wb["ROI_Capital"]["I2"].value, (int, float))
    notes = [str(wb["Cover"][f"B{r}"].value or "") for r in range(4, 20)]
    assert any("screening" in n.lower() or "formula" in n.lower() for n in notes)


def test_prefill_merges_in_place_keeps_eplus(tmp_path: Path):
    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"conditioned_floor_area_ft2": 140_000, "utility": {"elec_usd_per_kwh": 0.14, "gas_usd_per_therm": 0.9}},
        report={
            "savings_by_measure": [
                {
                    "measure_id": "ECM-AHU-SCHED-ALIGN",
                    "vs_baseline": {"kwh_saved": 12345.0, "therms_saved": 100.0},
                }
            ]
        },
    )
    xlsx = written["xlsx"]
    before = read_notebook_inputs(xlsx)
    assert before["area_ft2"] == 140_000
    assert before["elec_rate"] == 0.14

    wb0 = openpyxl.load_workbook(xlsx, data_only=False)
    assert wb0["EPlus_Results"]["B2"].value == 12345.0

    result = prefill_notebook_inputs(xlsx, overrides={"elec_rate": 0.22})
    assert "elec_rate" in result["updated"]
    after = read_notebook_inputs(xlsx)
    assert after["elec_rate"] == 0.22
    assert after["area_ft2"] == 140_000
    assert after["gas_rate"] == before["gas_rate"]

    wb1 = openpyxl.load_workbook(xlsx, data_only=False)
    assert wb1["EPlus_Results"]["B2"].value == 12345.0


def test_preview_shows_formulas_not_none(tmp_path: Path):
    written = build_and_save_notebook("controls_first", tmp_path, profile={"floor_area_ft2": 50_000})
    rows = preview_sheet_rows(written["xlsx"], "ROI_Capital", data_only=False)
    assert rows
    header = rows[0]
    assert "npv_usd_at_build" in header
    data = rows[1]
    assert data[1] is not None and str(data[1]).startswith("=")
    assert data[6] is not None and str(data[6]).startswith("=")
    assert isinstance(data[8], (int, float))


def test_summarize_resolves_package_and_ep_coverage(tmp_path: Path):
    written = build_and_save_notebook("schedules_economizer", tmp_path, profile={"floor_area_ft2": 80_000})
    man = summarize_notebook(written["xlsx"])
    assert man["package_id"] == "schedules_economizer"
    assert man["package_label"]
    assert man["ep_coverage"]["filled_rows"] == 0
    assert man["honesty"]["template_file"] in ("loaded", "scaffold_only")
    assert man["honesty"]["openfdd"] == "not_used"


def test_cli_prefill_elec_rate(tmp_path: Path):
    from wattlab.notebooks.cli import main

    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"conditioned_floor_area_ft2": 140_000, "utility": {"elec_usd_per_kwh": 0.14}},
    )
    rc = main(["prefill", "--xlsx", str(written["xlsx"]), "--elec-rate", "0.22"])
    assert rc == 0
    assert read_notebook_inputs(written["xlsx"])["elec_rate"] == 0.22
    assert read_notebook_inputs(written["xlsx"])["area_ft2"] == 140_000


def test_workbook_loads_template_when_present():
    """BUG-050: builds load templates/ecm_package_v1.xlsx when present."""
    import inspect

    from wattlab.notebooks import builder as b

    src = inspect.getsource(b.build_notebook_workbook)
    assert "load_workbook" in src
    assert "default_template_path" in src
    assert b.default_template_path().is_file()


def test_refresh_caches_and_show_formulas(tmp_path: Path):
    from openpyxl import load_workbook

    from wattlab.notebooks.builder import refresh_notebook_caches
    from wattlab.notebooks.cli import main

    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"conditioned_floor_area_ft2": 140_000, "utility": {"elec_usd_per_kwh": 0.14}},
    )
    xlsx = written["xlsx"]
    wb0 = load_workbook(xlsx, data_only=False)
    assert str(wb0["ROI_Capital"]["B2"].value).startswith("=H")
    assert str(wb0["ROI_Capital"]["G2"].value).startswith("=IF")

    prefill_notebook_inputs(xlsx, overrides={"elec_rate": 0.30})
    result = refresh_notebook_caches(xlsx)
    assert result["updated_cells"] >= 1
    wb1 = load_workbook(xlsx, data_only=False)
    assert str(wb1["ROI_Capital"]["B2"].value).startswith("=H")
    assert str(wb1["ROI_Capital"]["G2"].value).startswith("=IF")
    assert isinstance(wb1["ROI_Capital"]["I2"].value, (int, float))
    assert read_notebook_inputs(xlsx)["area_ft2"] == 140_000
    assert read_notebook_inputs(xlsx)["elec_rate"] == 0.30

    formulas = show_formulas(xlsx, sheet="ROI_Capital")
    assert "ROI_Capital" in formulas["sheets"]
    assert any(v.startswith("=") for v in formulas["sheets"]["ROI_Capital"].values())

    assert main(["show-formulas", "--xlsx", str(xlsx), "--sheet", "ROI_Capital"]) == 0
    assert main(["refresh-caches", "--xlsx", str(xlsx)]) == 0


def test_manifest_includes_formula_cells(tmp_path: Path):
    written = build_and_save_notebook("controls_first", tmp_path, profile={"floor_area_ft2": 50_000})
    man = summarize_notebook(written["xlsx"])
    assert "formula_cells" in man
    assert "ROI_Capital" in man["formula_cells"]
    assert man["honesty"]["esco_kwh_therms"] == "excel_formulas_for_subset_else_baked"
    assert "ECM-AHU-SCHED-ALIGN" in man["formula_backed_measures"]


def test_agent_build_formula_esco_and_cli(tmp_path: Path):
    from wattlab.notebooks.cli import main

    written = agent_build_notebook(
        "controls_first",
        tmp_path,
        profile={
            "display_name": "Liberty Building 100",
            "conditioned_floor_area_ft2": 140_000,
            "fan_hp": 50,
            "cooling_tons": 250,
        },
        measure_ids=[
            "ECM-AHU-SCHED-ALIGN",
            "ECM-PREMIUM-FAN-VFD",
            "ECM-CHILLER-LOCKOUT",
            "ECM-SENSOR-CALIBRATION",
        ],
    )
    wb = openpyxl.load_workbook(written["xlsx"], data_only=False)
    esco = wb["ESCO_Calcs"]
    by_mid = {}
    for r in range(2, (esco.max_row or 1) + 1):
        mid = esco.cell(r, 1).value
        if mid:
            by_mid[str(mid)] = (esco.cell(r, 2).value, esco.cell(r, 6).value)
    for mid in ("ECM-AHU-SCHED-ALIGN", "ECM-PREMIUM-FAN-VFD", "ECM-CHILLER-LOCKOUT"):
        assert str(by_mid[mid][0]).startswith("=")
        assert "Excel formula" in str(by_mid[mid][1])
    assert isinstance(by_mid["ECM-SENSOR-CALIBRATION"][0], (int, float))
    assert "proxy" in str(by_mid["ECM-SENSOR-CALIBRATION"][1]).lower()
    assert "inp_elec_rate" in str(esco["E2"].value)

    rc = main(
        [
            "agent-build",
            "--package",
            "controls_first",
            "--ecms",
            "ECM-AHU-SCHED-ALIGN,ECM-CHILLER-LOCKOUT",
            "--out",
            str(tmp_path / "cli_out"),
        ]
    )
    assert rc == 0
    assert (tmp_path / "cli_out" / "controls_first.xlsx").is_file()


def test_sync_from_twin_soft(tmp_path: Path):
    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"floor_area_ft2": 50_000, "display_name": "X"},
    )
    run = tmp_path / "twin_run"
    run.mkdir()
    result = sync_notebook_from_twin(written["xlsx"], twin_run=run)
    assert result["updated_rows"] == 0
    assert "no savings_by_measure" in result["note"]

    (run / "report.json").write_text(
        '{"savings_by_measure":[{"measure_id":"ECM-AHU-SCHED-ALIGN","vs_baseline":{"kwh_saved":99,"therms_saved":1}}]}',
        encoding="utf-8",
    )
    result2 = sync_notebook_from_twin(written["xlsx"], twin_run=run)
    assert result2["updated_rows"] >= 1
    wb = openpyxl.load_workbook(written["xlsx"], data_only=False)
    assert wb["EPlus_Results"]["B2"].value == 99


def test_formula_esco_constants_present():
    assert set(FORMULA_ESCO_KWH) >= {
        "ECM-AHU-SCHED-ALIGN",
        "ECM-PREMIUM-FAN-VFD",
        "ECM-CHILLER-LOCKOUT",
    }
