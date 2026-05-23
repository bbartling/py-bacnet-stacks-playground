"""Per-rule fault analytics for dashboard history window."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import fault_analytics_from_series  # noqa: E402


class TestFaultAnalytics(unittest.TestCase):
    def test_counts_and_elapsed_sorted_by_hits(self) -> None:
        rows = [{"ts_ms": i * 10_000} for i in range(6)]
        flags_a = [0, 1, 1, 0, 1, 0]
        flags_b = [1, 1, 1, 1, 0, 0]
        rules = [
            {"id": "rule_a", "title": "Rule A", "color": "#ff0000"},
            {"id": "rule_b", "title": "Rule B", "color": "#00ff00"},
        ]
        out = fault_analytics_from_series(
            {"rule_a": flags_a, "rule_b": flags_b}, rows, rules
        )
        self.assertEqual([x["id"] for x in out], ["rule_b", "rule_a"])
        by_id = {x["id"]: x for x in out}
        self.assertEqual(by_id["rule_a"]["count"], 3)
        self.assertEqual(by_id["rule_b"]["count"], 4)
        # rule_a: intervals at i=1,2,4 → 10s + 10s + 10s (last uses period)
        self.assertEqual(by_id["rule_a"]["elapsed_ms"], 30_000)
        self.assertEqual(by_id["rule_b"]["elapsed_ms"], 40_000)

    def test_skips_empty_flag_series(self) -> None:
        rows = [{"ts_ms": 0}, {"ts_ms": 10_000}]
        out = fault_analytics_from_series(
            {"quiet": []},
            rows,
            [{"id": "quiet", "title": "Quiet"}],
        )
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
