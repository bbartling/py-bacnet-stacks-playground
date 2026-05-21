"""Rows enriched with adaptive rolling avg before evaluate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import (  # noqa: E402
    attach_adaptive_rolling_avg,
    compile_evaluate,
    prepare_rows_for_evaluate,
    sweep_rule,
)


class TestRowEnrich(unittest.TestCase):
    def test_rolling_fields_on_rows(self) -> None:
        rows = [
            {"row": 0, "ts_ms": 0, "ts": "t0", "degF": 70.0, "degC": 21.0},
            {"row": 1, "ts_ms": 10_000, "ts": "t1", "degF": 80.0, "degC": 26.0},
            {"row": 2, "ts_ms": 20_000, "ts": "t2", "degF": 90.0, "degC": 32.0},
        ]
        attach_adaptive_rolling_avg(rows)
        self.assertEqual(rows[0]["degF_raw"], 70.0)
        self.assertEqual(rows[2]["degF_rolling_avg"], 80.0)
        self.assertEqual(rows[0]["rolling_window_samples"], 6)
        self.assertEqual(rows[0]["sample_period_ms"], 10_000)

    def test_evaluate_can_use_rolling_avg_field(self) -> None:
        rows = [
            {"row": i, "ts_ms": i * 10_000, "ts": f"t{i}", "degF": 70.0 if i < 8 else 90.0, "degC": 21.0}
            for i in range(12)
        ]
        code = """def evaluate(row, cfg, prev_row=None, rows=None):
    return row["degF_rolling_avg"] > cfg["bounds_high_f"]
"""
        flags, _ = sweep_rule(code, {"bounds_high_f": 80}, rows, capture_print=False)
        self.assertGreater(sum(flags), 0)


class TestNumpySandbox(unittest.TestCase):
    def test_numpy_import_in_rule(self) -> None:
        from playground_core import NUMPY_AVAILABLE

        if not NUMPY_AVAILABLE:
            self.skipTest("numpy not installed locally")
        code = """import numpy as np
def evaluate(row, cfg, prev_row=None, rows=None):
    return bool(np.isfinite(row["degF"]))
"""
        fn = compile_evaluate(code)
        row = {
            "row": 0,
            "ts_ms": 0,
            "ts": "t",
            "degF": 72.0,
            "degF_raw": 72.0,
            "degF_rolling_avg": 72.0,
        }
        self.assertTrue(fn(row, {}, None, [row]))


if __name__ == "__main__":
    unittest.main()
