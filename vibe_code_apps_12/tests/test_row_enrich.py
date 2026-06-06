"""Rows enriched with time-based rolling avg (chart aux; rules use Arrow masks)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
_TESTS = Path(__file__).resolve().parent
for p in (_WEB, _TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arrow_rules import ARROW_OOB  # noqa: E402
from playground_core import attach_rolling_avg, prepare_rows_for_evaluate, sweep_rule  # noqa: E402


class TestRowEnrich(unittest.TestCase):
    def test_rolling_fields_on_rows_one_minute(self) -> None:
        rows = [
            {"row": 0, "ts_ms": 0, "ts": "t0", "degF": 70.0, "degC": 21.0, "temp": 70.0},
            {"row": 1, "ts_ms": 10_000, "ts": "t1", "degF": 80.0, "degC": 26.0, "temp": 80.0},
            {"row": 2, "ts_ms": 20_000, "ts": "t2", "degF": 90.0, "degC": 32.0, "temp": 90.0},
        ]
        attach_rolling_avg(rows, minutes=1)
        self.assertEqual(rows[0]["temp_raw"], 70.0)
        self.assertEqual(rows[2]["degF_rolling_avg"], 80.0)
        self.assertEqual(rows[0]["rolling_avg_minutes"], 1)
        self.assertEqual(rows[0]["samples_in_avg"], 1)
        self.assertEqual(rows[2]["samples_in_avg"], 3)
        self.assertEqual(rows[0]["sample_period_ms"], 10_000)

    def test_five_minute_window_includes_more_samples(self) -> None:
        rows = [
            {"row": i, "ts_ms": i * 10_000, "ts": f"t{i}", "degF": 70.0, "degC": 21.0, "temp": 70.0}
            for i in range(40)
        ]
        attach_rolling_avg(rows, minutes=1)
        attach_rolling_avg(rows, minutes=5)
        self.assertLess(rows[-1]["samples_in_avg"], 40)
        self.assertGreater(rows[-1]["samples_in_avg"], rows[0]["samples_in_avg"])

    def test_arrow_oob_uses_rolling_avg_from_cfg(self) -> None:
        rows = [
            {"row": i, "ts_ms": i * 10_000, "ts": f"t{i}", "degF": 70.0 if i < 8 else 90.0, "degC": 21.0, "temp": 70.0 if i < 8 else 90.0}
            for i in range(12)
        ]
        flags, _ = sweep_rule(
            ARROW_OOB,
            {"bounds_high": 80, "bounds_low": 65, "rolling_avg_minutes": 1},
            rows,
            capture_print=False,
        )
        self.assertGreater(sum(flags), 0)

    def test_prepare_recomputes_when_minutes_change(self) -> None:
        rows = [
            {"row": 0, "ts_ms": 0, "ts": "t0", "degF": 50.0, "degC": 10.0, "temp": 50.0},
            {"row": 1, "ts_ms": 120_000, "ts": "t1", "degF": 90.0, "degC": 32.0, "temp": 90.0},
        ]
        prepare_rows_for_evaluate(rows, 1)
        self.assertEqual(rows[1]["degF_rolling_avg"], 90.0)
        prepare_rows_for_evaluate(rows, 5)
        self.assertEqual(rows[1]["rolling_avg_minutes"], 5)
        self.assertEqual(rows[1]["degF_rolling_avg"], 70.0)


if __name__ == "__main__":
    unittest.main()
