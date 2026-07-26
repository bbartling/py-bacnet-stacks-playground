"""Engineering notebook builder / prefill / validate / preview (BUG-030–037)."""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from wattlab.notebooks.builder import (
    build_and_save_notebook,
    build_notebook_workbook,
    prefill_notebook_inputs,
    preview_sheet_rows,
    read_notebook_inputs,
    refresh_notebook_caches,
    show_formulas,
    summarize_notebook,
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
    # BUG-035: B mirrors H formula
    assert str(wb["ROI_Capital"]["B2"].value).startswith("=H")
    assert "inp_usd_per_ft2" in str(wb["ROI_Capital"]["H2"].value)
    # BUG-032: NPV is live formula, cache in I
    assert str(wb["ROI_Capital"]["G2"].value).startswith("=IF")
    assert isinstance(wb["ROI_Capital"]["I2"].value, (int, float))
    # Cover honesty mentions scaffold / proxies
    cover_note = str(wb["Cover"]["B13"].value or wb["Cover"]["B14"].value or "")
    # find Note row
    notes = [str(wb["Cover"][f"B{r}"].value or "") for r in range(4, 20)]
    assert any("scaffold" in n.lower() or "proxies" in n.lower() for n in notes)


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
    ep_kwh = wb0["EPlus_Results"]["B2"].value
    assert ep_kwh == 12345.0

    result = prefill_notebook_inputs(xlsx, overrides={"elec_rate": 0.22})
    assert "elec_rate" in result["updated"]
    after = read_notebook_inputs(xlsx)
    assert after["elec_rate"] == 0.22
    assert after["area_ft2"] == 140_000  # not wiped to 50000
    assert after["gas_rate"] == before["gas_rate"]

    wb1 = openpyxl.load_workbook(xlsx, data_only=False)
    assert wb1["EPlus_Results"]["B2"].value == 12345.0


def test_preview_shows_formulas_not_none(tmp_path: Path):
    written = build_and_save_notebook("controls_first", tmp_path, profile={"floor_area_ft2": 50_000})
    rows = preview_sheet_rows(written["xlsx"], "ROI_Capital", data_only=False)
    assert rows
    # header + data: cost / npv cells should be formula strings, not None
    header = rows[0]
    assert "npv_usd_at_build" in header
    data = rows[1]
    # B implementation_cost
    assert data[1] is not None and str(data[1]).startswith("=")
    # G npv formula
    assert data[6] is not None and str(data[6]).startswith("=")
    # I cache numeric
    assert isinstance(data[8], (int, float))


def test_summarize_resolves_package_and_ep_coverage(tmp_path: Path):
    written = build_and_save_notebook("schedules_economizer", tmp_path, profile={"floor_area_ft2": 80_000})
    man = summarize_notebook(written["xlsx"])  # no package= arg (BUG-042)
    assert man["package_id"] == "schedules_economizer"
    assert man["package_label"]
    assert man["ep_coverage"]["filled_rows"] == 0
    assert man["honesty"]["template_file"] == "scaffold_only"


def test_cli_prefill_elec_rate(tmp_path: Path):
    from wattlab.notebooks.cli import main

    written = build_and_save_notebook(
        "controls_first",
        tmp_path,
        profile={"conditioned_floor_area_ft2": 140_000, "utility": {"elec_usd_per_kwh": 0.14}},
    )
    rc = main(
        [
            "prefill",
            "--xlsx",
            str(written["xlsx"]),
            "--elec-rate",
            "0.22",
        ]
    )
    assert rc == 0
    assert read_notebook_inputs(written["xlsx"])["elec_rate"] == 0.22
    assert read_notebook_inputs(written["xlsx"])["area_ft2"] == 140_000


def test_workbook_does_not_load_template_file():
    """BUG-033: builds are Workbook() — template path unused at runtime."""
    import inspect

    from wattlab.notebooks import builder as b

    src = inspect.getsource(b.build_notebook_workbook)
    assert "load_workbook" not in src
    assert "Workbook()" in src


def test_refresh_caches_and_show_formulas(tmp_path: Path):
    from openpyxl import load_workbook

    from wattlab.notebooks.builder import refresh_notebook_caches, show_formulas
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
    i_before = wb0["ROI_Capital"]["I2"].value

    prefill_notebook_inputs(xlsx, overrides={"elec_rate": 0.30})
    result = refresh_notebook_caches(xlsx)
    assert result["updated_cells"] >= 1
    wb1 = load_workbook(xlsx, data_only=False)
    # Formulas preserved
    assert str(wb1["ROI_Capital"]["B2"].value).startswith("=H")
    assert str(wb1["ROI_Capital"]["G2"].value).startswith("=IF")
    # Cache column refreshed (may change with higher elec rate)
    assert wb1["ROI_Capital"]["I2"].value is not None
    assert isinstance(wb1["ROI_Capital"]["I2"].value, (int, float))
    # Area not wiped
    assert read_notebook_inputs(xlsx)["area_ft2"] == 140_000
    assert read_notebook_inputs(xlsx)["elec_rate"] == 0.30

    formulas = show_formulas(xlsx, sheet="ROI_Capital")
    assert "ROI_Capital" in formulas["sheets"]
    assert any(v.startswith("=") for v in formulas["sheets"]["ROI_Capital"].values())

    rc = main(["show-formulas", "--xlsx", str(xlsx), "--sheet", "ROI_Capital"])
    assert rc == 0
    rc2 = main(["refresh-caches", "--xlsx", str(xlsx)])
    assert rc2 == 0
    _ = i_before  # silence unused when NPV equals


def test_manifest_includes_formula_cells(tmp_path: Path):
    written = build_and_save_notebook("controls_first", tmp_path, profile={"floor_area_ft2": 50_000})
    man = summarize_notebook(written["xlsx"])
    assert "formula_cells" in man
    assert "ROI_Capital" in man["formula_cells"]
    assert man["honesty"]["esco_kwh_therms"] == "baked_at_build"
