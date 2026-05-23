"""Verbose test window trace for Rule Lab."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import ONE_HOUR_MS, readings_to_rows, window_trace_events  # noqa: E402


class TestWindowTrace(unittest.TestCase):
    def test_trace_finds_full_hour_window(self) -> None:
        n = 400
        readings = [
            {"ts_ms": 1_000_000 + i * 10_000, "degF": 70.0 + (0.01 if i % 2 else 0.0)}
            for i in range(n)
        ]
        rows = readings_to_rows(readings)
        from playground_core import prepare_rows_for_evaluate

        prepare_rows_for_evaluate(rows, 1, temp_unit="imperial")
        events = window_trace_events(rows, window_ms=ONE_HOUR_MS, sample_every=50)
        self.assertTrue(events)
        header = events[0]["text"]
        self.assertIn("[trace]", header)
        self.assertIn("spread min=", header)

    def test_trace_empty_when_window_too_short(self) -> None:
        rows = readings_to_rows([{"ts_ms": 1_000_000, "degF": 70.0}])
        from playground_core import prepare_rows_for_evaluate

        prepare_rows_for_evaluate(rows, 1, temp_unit="imperial")
        events = window_trace_events(rows, window_ms=ONE_HOUR_MS)
        self.assertEqual(len(events), 1)
        self.assertIn("no full", events[0]["text"])


if __name__ == "__main__":
    unittest.main()
