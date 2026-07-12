"""Regression: Results-by-equipment table must sort without unhashable list crash."""

from __future__ import annotations

import pandas as pd

from streamlit_app import _device_results_table


def test_device_results_table_sorts_with_list_missing_roles():
    summary = pd.DataFrame(
        [
            {
                "rule_id": "VAV-10",
                "equipment_id": "VAV_1",
                "status": "NOT_APPLICABLE_EQUIPMENT_TYPE",
                "fault_hours": None,
                "fault_pct": None,
                "missing_roles": [],
                "notes": "",
            },
            {
                "rule_id": "VAV-2",
                "equipment_id": "VAV_1",
                "status": "FAULT",
                "fault_hours": 1.0,
                "fault_pct": 10.0,
                "missing_roles": ["reheat_valve_pct"],
                "notes": "x",
            },
            {
                "rule_id": "VAV-1",
                "equipment_id": "VAV_1",
                "status": "PASS",
                "fault_hours": 0.0,
                "fault_pct": 0.0,
                "missing_roles": ["a", "b"],  # list-valued cells must not break sort
                "notes": "",
            },
            {
                "rule_id": "AHU-SATDEV",
                "equipment_id": "VAV_1",
                "status": "SKIPPED_MISSING_ROLES",
                "fault_hours": None,
                "fault_pct": None,
                "missing_roles": ["sat", "sat_sp"],
                "notes": "",
            },
        ]
    )
    tbl = _device_results_table(summary, "VAV_1")
    assert list(tbl["rule_id"]) == ["VAV-2", "VAV-1", "AHU-SATDEV", "VAV-10"]
    assert list(tbl["status"]) == [
        "FAULT",
        "PASS",
        "SKIPPED_MISSING_ROLES",
        "NOT_APPLICABLE_EQUIPMENT_TYPE",
    ]
