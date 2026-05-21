"""Unit tests for Rule Lab sandbox (no AWS). Run: python3 -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import (  # noqa: E402
    compile_evaluate,
    eval_rows_preview,
    lint_python,
    prepare_rows_for_evaluate,
    readings_to_rows,
    sweep_rule,
)


class TestLint(unittest.TestCase):
    def test_valid_syntax(self) -> None:
        code = "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        self.assertTrue(lint_python(code)["ok"])

    def test_invalid_syntax(self) -> None:
        self.assertFalse(lint_python("def evaluate(:\n")["ok"])

    def test_numpy_import_allowed(self) -> None:
        code = "import numpy as np\ndef evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        issues = lint_python(code)["issues"]
        self.assertFalse(any(i["severity"] == "error" for i in issues))


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
        cfg = {"bounds_high_f": 80.0, "bounds_low_f": 65.0}
        flags, events = sweep_rule(code, cfg, rows, capture_print=False)
        self.assertGreater(sum(flags), 0)
        types = {e["type"] for e in events}
        self.assertIn("summary", types)

    def test_sweep_enriches_rows_with_rolling_avg(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 70.0, "degC": 21.0}
            for i in range(8)
        ]
        rows = readings_to_rows(readings)
        code = "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        sweep_rule(code, {}, rows, capture_print=False)
        self.assertIn("degF_rolling_avg", rows[0])
        self.assertIn("sample_period_ms", rows[0])

    def test_eval_rows_preview_limits(self) -> None:
        readings = [
            {"ts_ms": i * 1000, "degF": 70.0 + i, "degC": 21.0}
            for i in range(50)
        ]
        rows = prepare_rows_for_evaluate(readings_to_rows(readings))
        preview = eval_rows_preview(rows, limit=10)
        self.assertEqual(len(preview), 10)
        self.assertIn("degF_rolling_avg", preview[-1])

    def test_prepare_idempotent(self) -> None:
        rows = readings_to_rows([{"ts_ms": 0, "degF": 70.0, "degC": 21.0}, {"ts_ms": 10000, "degF": 71.0, "degC": 21.0}])
        prepare_rows_for_evaluate(rows)
        avg_first = rows[0]["degF_rolling_avg"]
        prepare_rows_for_evaluate(rows)
        self.assertEqual(rows[0]["degF_rolling_avg"], avg_first)


class TestImportSandbox(unittest.TestCase):
    def test_blocked_import_raises(self) -> None:
        code = "import pandas as pd\ndef evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        with self.assertRaises(ImportError):
            compile_evaluate(code)


if __name__ == "__main__":
    unittest.main()
