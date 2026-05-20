"""Unit tests for built-in FDD rules (no AWS). Run: python3 -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from fdd_rules import RuleConfig, evaluate_all  # noqa: E402
from playground_core import rolling_window_flags  # noqa: E402


def _readings(deg_f: list[float], step_ms: int = 10_000) -> list[dict]:
    return [
        {"ts_ms": i * step_ms, "degF": t, "degC": (t - 32) * 5 / 9}
        for i, t in enumerate(deg_f)
    ]


class TestRollingWindowHelper(unittest.TestCase):
    """Helper exists for cookbook; not applied in evaluate_all anymore."""

    def test_requires_consecutive_hits(self) -> None:
        raw = [False, True, True, True, True, True, True]
        flags = rolling_window_flags(raw, 6)
        self.assertEqual(flags[:5], [0, 0, 0, 0, 0])
        self.assertEqual(flags[6], 1)


class TestBoundsRule(unittest.TestCase):
    def test_out_of_bounds_flags_instant(self) -> None:
        temps = [70.0] * 3 + [90.0] * 3
        cfg = RuleConfig(bounds_low_f=65, bounds_high_f=80)
        series = evaluate_all(_readings(temps), cfg)
        self.assertEqual(series["temp_out_of_bounds_flag"], [0, 0, 0, 1, 1, 1])


class TestFlatlineRule(unittest.TestCase):
    def test_flatline_detects_stuck_sensor(self) -> None:
        temps = [70.0] * 25
        cfg = RuleConfig(flatline_window=18, flatline_tolerance_f=0.05)
        series = evaluate_all(_readings(temps), cfg)
        self.assertGreater(sum(series["temp_flatline_flag"]), 0)


class TestRateRule(unittest.TestCase):
    def test_fast_step_flags_rate(self) -> None:
        temps = [70.0] * 5 + [85.0] * 5
        cfg = RuleConfig(max_f_per_minute=2.0)
        series = evaluate_all(_readings(temps), cfg)
        self.assertGreater(sum(series["temp_rate_per_minute_flag"]), 0)


if __name__ == "__main__":
    unittest.main()
