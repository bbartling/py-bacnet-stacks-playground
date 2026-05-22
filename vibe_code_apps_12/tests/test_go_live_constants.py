"""Go live uses fixed 6 h batches and 7 d max lookback."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from playground_core import (  # noqa: E402
    GO_LIVE_BATCH_HOURS,
    GO_LIVE_MAX_LOOKBACK_HOURS,
    GO_LIVE_OVERLAP_MINUTES,
)


class TestGoLiveConstants(unittest.TestCase):
    def test_hard_coded_batch_and_window(self) -> None:
        self.assertEqual(GO_LIVE_BATCH_HOURS, 6)
        self.assertEqual(GO_LIVE_MAX_LOOKBACK_HOURS, 168)
        self.assertEqual(GO_LIVE_OVERLAP_MINUTES, 15)
        # 7 d at 6 h per batch => 28 chunks max
        self.assertEqual(GO_LIVE_MAX_LOOKBACK_HOURS // GO_LIVE_BATCH_HOURS, 28)


if __name__ == "__main__":
    unittest.main()
