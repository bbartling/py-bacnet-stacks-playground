"""FDD status payload must fit DynamoDB size limits."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import slim_fdd_summary  # noqa: E402


class TestSlimFddSummary(unittest.TestCase):
    def test_strips_large_series(self) -> None:
        big = {
            "fdd_status": "NORMAL",
            "ts_ms": list(range(50000)),
            "flag_series": {"a": [1] * 50000},
            "aux_series": {"x": [1.0] * 50000},
            "flag_counts": {"a": 3},
            "sample_count": 50000,
        }
        slim = slim_fdd_summary(big)
        self.assertNotIn("ts_ms", slim)
        self.assertNotIn("flag_series", slim)
        self.assertNotIn("aux_series", slim)
        self.assertEqual(slim["flag_counts"], {"a": 3})
        payload = json.dumps(slim)
        self.assertLess(len(payload), 400_000)


if __name__ == "__main__":
    unittest.main()
