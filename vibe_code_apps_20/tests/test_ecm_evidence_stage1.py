"""ENH-VIBE-002 / Stage-1 evidence: full-parity merge + evidence export."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.ecm.compare import (
    build_compare_from_cascade,
    discover_notebook_xlsx,
    empty_compare_stub,
    load_compare,
    merge_full_parity_ss,
    write_compare,
)
from wattlab.ecm.evidence_export import (
    EVIDENCE_SCHEMA_VERSION,
    build_dual_rail_sizing_inputs,
    engineering_input,
    export_ecm_simulation_evidence,
    validate_engineering_inputs,
)


def test_merge_full_parity_ss_fills_ss(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    compare = build_compare_from_cascade(
        {
            "twin_run": "t1",
            "savings_by_measure": [
                {
                    "measure_id": "ECM-DSP-RESET",
                    "vs_baseline": {
                        "kwh_saved": 1000.0,
                        "therms_saved": 0.0,
                        "cost_saved_usd": 120.0,
                    },
                }
            ],
        },
        measure_ids=["ECM-DSP-RESET"],
        twin_run="t1",
        profile={"conditioned_floor_area_ft2": 100_000},
    )
    assert compare["measures"][0]["ss_kwh"] is None

    parity = {
        "measures": [
            {
                "measure_id": "ECM-DSP-RESET",
                "ss_kwh": 950.0,
                "ss_therms": 2.5,
                "ss_usd": 114.0,
                "payback_yr_ss": 4.2,
                "roi_ss": 0.24,
            }
        ]
    }
    (reports / "ecm_full_parity_compare.json").write_text(
        json.dumps(parity) + "\n", encoding="utf-8"
    )

    merged = merge_full_parity_ss(compare, reports)
    row = merged["measures"][0]
    assert row["ss_kwh"] == 950.0
    assert row["ss_therms"] == 2.5
    assert row["ss_usd"] == 114.0
    assert row["payback_yr_ss"] == 4.2
    assert row["roi_ss"] == 0.24
    assert merged["spreadsheet"]["status"] == "full_parity"
    assert row["status"] == "ss_ep_ready"


def test_merge_full_parity_ss_noop_without_file(tmp_path: Path):
    stub = empty_compare_stub(measure_ids=["ECM-SAT-RESET"])
    out = merge_full_parity_ss(stub, tmp_path / "reports")
    assert out["spreadsheet"]["status"] == "pending_external"
    assert all(m["ss_kwh"] is None for m in out["measures"])


def test_load_compare_merges_full_parity(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    stub = empty_compare_stub(measure_ids=["ECM-DSP-RESET"])
    cpath = write_compare(reports / "ecm_compare.json", stub)
    (reports / "ecm_full_parity_compare.json").write_text(
        json.dumps(
            {
                "measures": [
                    {"measure_id": "ECM-DSP-RESET", "ss_kwh": 10.0, "ss_usd": 1.2}
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = load_compare(cpath, reports_dir=reports)
    assert loaded is not None
    assert loaded["measures"][0]["ss_kwh"] == 10.0


def test_discover_notebook_xlsx_recursive(tmp_path: Path):
    nb = tmp_path / "notebooks"
    (nb / "full_parity_ecm").mkdir(parents=True)
    top = nb / "legacy.xlsx"
    nested = nb / "full_parity_ecm" / "ECM_FULL_PARITY.xlsx"
    lock = nb / "full_parity_ecm" / "~$lock.xlsx"
    top.write_bytes(b"PK")
    nested.write_bytes(b"PK")
    lock.write_bytes(b"PK")
    found = discover_notebook_xlsx(nb)
    names = {p.name for p in found}
    assert names == {"legacy.xlsx", "ECM_FULL_PARITY.xlsx"}
    assert any("full_parity_ecm" in p.parts for p in found)


def test_evidence_export_schema_and_dual_rail(tmp_path: Path):
    cascade = {
        "twin_run": "synth_twin",
        "run_id": "cascade_1",
        "report_path": str(tmp_path / "wattlab_report.json"),
        "savings_by_measure": [
            {
                "measure_id": "ECM-SAT-RESET",
                "run_id": "sat_1",
                "vs_baseline": {"kwh_saved": 500.0, "therms_saved": 10.0},
            }
        ],
        "weather_suitability": {"mode": "ACTUAL_YEAR_CALIBRATION"},
    }
    sizing = {"fan_hp": 75.0, "ep_fan_hp": 72.5, "cooling_tons": 180.0}
    result = export_ecm_simulation_evidence(
        tmp_path,
        cascade_report=cascade,
        sizing=sizing,
        profile={"building_type": "office", "floor_area_ft2": 100000},
        ss_fan_hours=4000.0,
        ep_fan_hours=5200.0,
    )
    assert result["ok"]
    evidence = json.loads(Path(result["evidence_path"]).read_text(encoding="utf-8"))
    assert evidence["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert evidence["schema_version"] == "ecm_simulation_evidence_v1"
    assert "equipment_autosizing" in evidence
    assert evidence["individual_measures"][0]["measure_id"] == "ECM-SAT-RESET"
    assert evidence["individual_measures"][0]["baseline_run_id"]
    assert evidence["individual_measures"][0]["comparison_mode"]
    assert evidence["individual_measures"][0]["result_scope"]

    inputs_doc = json.loads(Path(result["inputs_path"]).read_text(encoding="utf-8"))
    ids = {i["input_id"] for i in inputs_doc["inputs"]}
    assert "ss_fan_hp" in ids
    assert "ep_fan_hp" in ids
    assert validate_engineering_inputs(inputs_doc["inputs"]) == []


def test_reject_missing_assumption_note_for_agent_inferred_hours():
    bad = engineering_input(
        input_id="ss_sched_hours_saved",
        display_name="Sched hours saved",
        value=2500,
        unit="h/yr",
        rail="spreadsheet",
        source_type="agent_inferred",
        assumption_note="",
    )
    issues = validate_engineering_inputs([bad])
    assert issues
    assert "assumption_note" in issues[0]

    good = engineering_input(
        input_id="ss_sched_hours_saved",
        display_name="Sched hours saved",
        value=2500,
        unit="h/yr",
        rail="spreadsheet",
        source_type="agent_inferred",
        assumption_note="FLH back-calc from cascade; not AMY calendar FanAvail.",
        assumption_method="flh_from_cascade",
    )
    assert validate_engineering_inputs([good]) == []


def test_dual_rail_pair_helper():
    inputs = build_dual_rail_sizing_inputs(ss_fan_hp=80.0, ep_fan_hp=78.0)
    ids = {i["input_id"] for i in inputs}
    assert "ss_fan_hp" in ids and "ep_fan_hp" in ids
    assert validate_engineering_inputs(inputs) == []


def test_evidence_dry_run_ok(tmp_path: Path):
    result = export_ecm_simulation_evidence(
        tmp_path,
        cascade_report={"savings_by_measure": []},
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["evidence_path"] is None
    assert not (tmp_path / "ecm_simulation_evidence.json").exists()
