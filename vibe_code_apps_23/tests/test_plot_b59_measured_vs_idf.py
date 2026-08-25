"""Tests for measured-vs-IDF discrepancy figure pack (frozen JSON only)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts" / "plot_b59_measured_vs_idf.py"
    spec = importlib.util.spec_from_file_location("plot_b59_measured_vs_idf", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]


def test_plot_b59_measured_vs_idf_pack(tmp_path: Path) -> None:
    out = tmp_path / "figures"
    manifest = _module().build_pack(
        comparison_path=ROOT / "config" / "b59_measured_vs_screening_idf.json",
        hvac_path=ROOT / "config" / "b59_hvac_operating_evidence.json",
        champion_path=ROOT / "scorecards" / "b59_2020_screening" / "champion_parameters.json",
        output_dir=out,
    )
    assert manifest["claim_status"] == "DISCREPANCY_AUDIT_NOT_CALIBRATED"
    assert (out / "measured_vs_idf_discrepancy_table.csv").is_file()
    assert (out / "fig01_severity_counts.png").is_file()
    assert (out / "fig02_rtu_sat_setpoint_vs_idf.png").is_file()
    assert (out / "fig03_rtu_airflow_capacity_delta.png").is_file()
    assert (out / "fig04_zone_setpoint_diversity_vs_idf.png").is_file()
    assert (out / "fig05_oa_fraction_vs_idf.png").is_file()
    payload = json.loads((out / "figure_manifest.json").read_text(encoding="utf-8"))
    assert payload["severity_counts"]["BLOCKING_CONTROL"] >= 1
