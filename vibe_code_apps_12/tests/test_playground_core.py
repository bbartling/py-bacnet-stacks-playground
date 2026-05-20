"""Unit tests for Rule Lab sandbox (no AWS). Run: python3 -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import lint_python, readings_to_rows, sweep_rule  # noqa: E402


class TestLint(unittest.TestCase):
    def test_valid_syntax(self) -> None:
        code = "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        self.assertTrue(lint_python(code)["ok"])

    def test_invalid_syntax(self) -> None:
        self.assertFalse(lint_python("def evaluate(:\n")["ok"])


class TestSweep(unittest.TestCase):
    def test_bounds_rule_sweep(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 90.0 if i >= 8 else 70.0, "degC": 21.0}
            for i in range(12)
        ]
        rows = readings_to_rows(readings)
        code = """def evaluate(row, cfg, prev_row=None, rows=None):
    return row["degF"] > cfg["bounds_high_f"]
"""
        cfg = {"bounds_high_f": 80.0, "bounds_low_f": 65.0, "rolling_window": 2}
        flags, events = sweep_rule(code, cfg, rows, capture_print=False)
        self.assertGreater(sum(flags), 0)
        types = {e["type"] for e in events}
        self.assertIn("summary", types)


if __name__ == "__main__":
    unittest.main()
