"""Tests for 1-minute rolling average enrichment."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import readings_to_rows, sweep_rule  # noqa: E402
from timeseries_enrich import attach_minute_rolling_avg  # noqa: E402


class TestMinuteRollingAvg(unittest.TestCase):
    def test_same_minute_shares_avg(self) -> None:
        rows = [
            {"row": 0, "ts_ms": 0, "ts": "t0", "degF": 70.0, "degC": 21.0},
            {"row": 1, "ts_ms": 10_000, "ts": "t1", "degF": 80.0, "degC": 26.0},
            {"row": 2, "ts_ms": 20_000, "ts": "t2", "degF": 90.0, "degC": 32.0},
        ]
        attach_minute_rolling_avg(rows, bucket_ms=60_000)
        self.assertEqual(rows[0]["degF_1min_avg"], 80.0)
        self.assertEqual(rows[2]["degF_1min_avg"], 80.0)
        self.assertEqual(rows[0]["degF_raw"], 70.0)
        self.assertEqual(rows[2]["degF_raw"], 90.0)

    def test_flag_index_matches_raw_timeline(self) -> None:
        readings = [
            {"ts_ms": i * 10_000, "degF": 70.0 if i < 5 else 90.0, "degC": 21.0}
            for i in range(10)
        ]
        rows = readings_to_rows(readings)
        code = """def evaluate(row, cfg, prev_row=None, rows=None):
    return rolling_avg_field(row, "degF") > cfg["bounds_high_f"]
"""
        flags, _ = sweep_rule(code, {"bounds_high_f": 80, "rolling_window": 1}, rows)
        self.assertEqual(len(flags), len(readings))


if __name__ == "__main__":
    unittest.main()
