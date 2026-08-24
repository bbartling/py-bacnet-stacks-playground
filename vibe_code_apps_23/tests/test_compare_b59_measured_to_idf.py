from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


def _module():
    path = Path(__file__).parents[1] / "scripts" / "compare_b59_measured_to_idf.py"
    spec = importlib.util.spec_from_file_location("compare_b59_measured_to_idf", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plant_loop_activity_is_a_scoped_proxy(tmp_path):
    path = tmp_path / "ashp_cw.csv"
    pd.DataFrame(
        {
            "date": ["2020-01-01 00:00", "2020-01-01 00:05", "2020-01-01 00:10"],
            "supply": [50.0, 44.0, 46.0],
            "return": [55.0, 50.0, 52.0],
            "flow": [0.0, 10.0, 20.0],
        }
    ).to_csv(path, index=False)
    result = _module()._plant_loop_evidence(path, supply="supply", return_="return", flow="flow")
    assert result["active_flow_fraction_of_valid_rows"] == pytest.approx(2 / 3)
    assert result["supply_temperature_degF_when_flow_active"]["median"] == 45.0
    assert "not proof" in result["runtime_claim_boundary"]


def test_markdown_renders_requested_comparison_table():
    comparison = {
        "comparison_rows": [
            {
                "domain": "SAT setpoint",
                "measured_or_runtime_evidence": "60°F",
                "screening_idf_configuration": "57.9°F",
                "difference_and_disposition": "Replay measured setpoint.",
                "severity": "MAJOR",
            }
        ],
        "decision": "Not calibrated.",
    }
    rendered = _module().render_markdown(comparison)
    assert "| Domain | Downloaded-data analytics | Current screening IDF |" in rendered
    assert "SAT setpoint" in rendered
    assert "Not calibrated." in rendered
