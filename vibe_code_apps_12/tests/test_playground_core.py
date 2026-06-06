"""Unit tests for Arrow Rule Lab sandbox (no AWS)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
_TESTS = Path(__file__).resolve().parent
for p in (_WEB, _TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arrow_rules import ARROW_FALSE, ARROW_OOB  # noqa: E402
from playground_core import (  # noqa: E402
    eval_rows_preview,
    lint_python,
    prepare_rows_for_evaluate,
    readings_to_rows,
    sweep_rule,
)


class TestLint(unittest.TestCase):
    def test_valid_arrow_rule(self) -> None:
        self.assertTrue(lint_python(ARROW_FALSE)["ok"])

    def test_invalid_syntax(self) -> None:
        self.assertFalse(lint_python("def apply_faults_arrow(:\n")["ok"])

    def test_legacy_evaluate_rejected(self) -> None:
        code = "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n"
        self.assertFalse(lint_python(code)["ok"])


class TestSweep(unittest.TestCase):
    def test_bounds_rule_sweep(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 90.0 if i >= 8 else 70.0, "degC": 21.0}
            for i in range(12)
        ]
        rows = readings_to_rows(readings)
        cfg = {"bounds_high": 80.0, "bounds_low": 65.0, "rolling_avg_minutes": 1}
        flags, events = sweep_rule(ARROW_OOB, cfg, rows, capture_print=False)
        self.assertGreater(sum(flags), 0)
        types = {e["type"] for e in events}
        self.assertIn("row", types)

    def test_sweep_enriches_rows_with_rolling_avg(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 70.0, "degC": 21.0}
            for i in range(8)
        ]
        rows = readings_to_rows(readings)
        sweep_rule(ARROW_FALSE, {}, rows, capture_print=False)
        self.assertIn("degF_rolling_avg", rows[0])
        self.assertEqual(rows[0]["rolling_avg_minutes"], 1)
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


if __name__ == "__main__":
    unittest.main()
