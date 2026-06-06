"""Chunked chart rule eval for long windows (Arrow-only)."""

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
    evaluate_rules_on_readings,
    evaluate_rules_on_readings_chunked,
)


def _readings(n: int, step_ms: int = 60_000) -> list[dict]:
    base = 1_700_000_000_000
    return [
        {"ts_ms": base + i * step_ms, "degF": 70.0, "degC": 21.1}
        for i in range(n)
    ]


class TestChartChunkedEval(unittest.TestCase):
    def test_chunked_matches_full_on_small_window(self) -> None:
        rules = [
            {
                "id": "high",
                "enabled": True,
                "config": {"bounds_high": 75.0, "bounds_low": 60.0, "rolling_avg_minutes": 1},
                "code": ARROW_OOB,
            }
        ]
        readings = _readings(40, step_ms=120_000)
        readings[-1]["degF"] = 90.0
        readings[-1]["degC"] = 32.2
        full, _ = evaluate_rules_on_readings(rules, readings)
        chunked, _ = evaluate_rules_on_readings_chunked(
            rules, readings, chunk_hours=1.0, overlap_minutes=15
        )
        self.assertEqual(full.get("high"), chunked.get("high"))

    def test_chunked_runs_more_than_one_chunk(self) -> None:
        rules = [
            {
                "id": "always",
                "enabled": True,
                "config": {},
                "code": ARROW_FALSE,
            }
        ]
        readings = _readings(420, step_ms=60_000)
        chunked, rows = evaluate_rules_on_readings_chunked(
            rules, readings, chunk_hours=1.0, overlap_minutes=5
        )
        self.assertEqual(len(rows), len(readings))
        self.assertEqual(len(chunked["always"]), len(readings))


if __name__ == "__main__":
    unittest.main()
