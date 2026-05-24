"""CSV export for dashboard readings + fault lanes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import build_readings_csv  # noqa: E402
from rules_defaults import default_custom_rules  # noqa: E402


class TestReadingsCsv(unittest.TestCase):
    def test_csv_includes_temp_and_fault_columns(self) -> None:
        readings = [
            {"ts_ms": 1_700_000_000_000, "ts_iso": "2023-11-14 22:13:20", "degF": 70.0, "degC": 21.1},
            {"ts_ms": 1_700_000_060_000, "ts_iso": "2023-11-14 22:14:20", "degF": 90.0, "degC": 32.2},
        ]
        rows = [
            {"degF_rolling_avg": 70.0},
            {"degF_rolling_avg": 80.0},
        ]
        rules = default_custom_rules()[:1]
        rid = rules[0]["id"]
        fault_plots = {rid: [0, 1]}
        csv_text = build_readings_csv(readings, rows, fault_plots, rules, fault_rule_ids=[rid])
        lines = csv_text.strip().split("\r\n")
        self.assertGreaterEqual(len(lines), 3)
        header = lines[0]
        self.assertIn("time_utc", header)
        self.assertIn("degF", header)
        self.assertIn("fault_", header)
        self.assertIn(",1", lines[2])

    def test_fault_filter_limits_columns(self) -> None:
        readings = [
            {"ts_ms": 1, "ts_iso": "2023-01-01 00:00:00", "degF": 70.0, "degC": 21.1},
        ]
        rules = default_custom_rules()[:2]
        fault_plots = {rules[0]["id"]: [1], rules[1]["id"]: [0]}
        csv_text = build_readings_csv(
            readings, [], fault_plots, rules, fault_rule_ids=[rules[0]["id"]]
        )
        header = csv_text.split("\r\n")[0]
        self.assertEqual(header.count("fault_"), 1)

    def test_empty_fault_filter_exports_no_fault_columns(self) -> None:
        readings = [
            {"ts_ms": 1, "ts_iso": "2023-01-01 00:00:00", "degF": 70.0, "degC": 21.1},
        ]
        rules = default_custom_rules()[:2]
        fault_plots = {rules[0]["id"]: [1], rules[1]["id"]: [0]}
        csv_text = build_readings_csv(readings, [], fault_plots, rules, fault_rule_ids=[])
        header = csv_text.split("\r\n")[0]
        self.assertEqual(header.count("fault_"), 0)


if __name__ == "__main__":
    unittest.main()
