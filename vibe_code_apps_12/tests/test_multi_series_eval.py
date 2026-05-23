"""Cross-sensor rule evaluation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import build_series_context, evaluate_rules_on_series, readings_to_rows  # noqa: E402


class TestMultiSeriesEval(unittest.TestCase):
    def test_build_series_context_aliases(self) -> None:
        series_map = {
            "sid-sat": [{"value": 70.0}, {"value": 72.0}],
            "sid-rat": [{"value": 65.0}, {"value": 66.0}],
        }
        ctx = build_series_context(series_map, 1, aliases={"SAT": "sid-sat", "RAT": "sid-rat"})
        self.assertEqual(ctx["SAT"]["current"], 72.0)
        self.assertEqual(ctx["RAT"]["current"], 66.0)

    def test_sat_rat_spread_rule(self) -> None:
        readings = [
            {"ts_ms": i * 60_000, "degF": 70.0 + i, "degC": 21.0}
            for i in range(4)
        ]
        rows = readings_to_rows(readings)
        series_map = {
            "sat": [{"ts_ms": r["ts_ms"], "value": 55.0} for r in rows],
            "rat": [{"ts_ms": r["ts_ms"], "value": 70.0} for r in rows],
        }
        rules = [
            {
                "id": "spread",
                "enabled": True,
                "config": {
                    "max_spread": 10.0,
                    "series_aliases": {"SAT": "sat", "RAT": "rat"},
                },
                "code": """def evaluate(row, cfg, prev_row=None, rows=None, series=None):
    sat = series["SAT"]["current"]
    rat = series["RAT"]["current"]
    if sat is None or rat is None:
        return False
    return abs(sat - rat) > cfg["max_spread"]
""",
            }
        ]
        flags = evaluate_rules_on_series(rules, rows, series_map)
        self.assertEqual(sum(flags["spread"]), len(rows))


if __name__ == "__main__":
    unittest.main()
