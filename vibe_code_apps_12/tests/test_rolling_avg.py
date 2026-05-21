"""Tests for time-based rolling avg on evaluate rows."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import (  # noqa: E402
    aux_series_from_rows,
    normalize_rolling_avg_minutes,
    prepare_rows_for_evaluate,
    readings_to_rows,
)


class TestRollingAvgMinutes(unittest.TestCase):
    def test_normalize_clamps_to_allowed(self) -> None:
        self.assertEqual(normalize_rolling_avg_minutes(5), 5)
        self.assertEqual(normalize_rolling_avg_minutes(7), 5)
        self.assertEqual(normalize_rolling_avg_minutes("10"), 10)

    def test_prepare_adds_rolling_avg(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 70.0 if i < 5 else 90.0, "degC": 21.0}
            for i in range(10)
        ]
        rows = prepare_rows_for_evaluate(readings_to_rows(readings), 1)
        self.assertIn("degF_rolling_avg", rows[0])
        self.assertEqual(rows[0]["rolling_avg_minutes"], 1)
        aux = aux_series_from_rows(rows)
        self.assertIn("degF_1min_avg", aux)
        self.assertEqual(len(aux["degF_1min_avg"]), 10)


if __name__ == "__main__":
    unittest.main()
