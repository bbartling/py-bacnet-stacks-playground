"""Arrow fault masks (rolling-window rules paint multiple rows natively)."""

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
from playground_core import readings_to_rows, sweep_rule  # noqa: E402


def _rows(n: int = 8) -> list[dict]:
    readings = [
        {"ts_ms": 1_000_000 + i * 60_000, "degF": 70.0 + (0.1 if i < 5 else 0.0)}
        for i in range(n)
    ]
    return readings_to_rows(readings)


class TestArrowFaultMasks(unittest.TestCase):
    def test_oob_flags_hot_samples(self) -> None:
        rows = _rows(8)
        rows[-1]["degF"] = 95.0
        rows[-1]["temp"] = 95.0
        flags, events = sweep_rule(
            ARROW_OOB,
            {"bounds_high": 80.0, "bounds_low": 65.0, "rolling_avg_minutes": 1},
            rows,
            capture_print=False,
        )
        self.assertGreater(sum(flags), 0)
        self.assertIn("row", {e["type"] for e in events})

    def test_false_rule_never_flags(self) -> None:
        rows = _rows(6)
        flags, _ = sweep_rule(ARROW_FALSE, {}, rows, capture_print=False)
        self.assertEqual(sum(flags), 0)


if __name__ == "__main__":
    unittest.main()
