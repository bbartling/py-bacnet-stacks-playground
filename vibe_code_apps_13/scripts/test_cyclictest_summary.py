#!/usr/bin/env python3
"""Unit tests for cyclictest_summary aggregation and host-risk assessment."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cyclictest_summary import (  # noqa: E402
    HOST_RISK_THRESHOLD_US,
    format_result_section,
    parse_cyclictest_text,
    summary_to_dict,
)

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "cyclictest"


class CyclictestSummaryTests(unittest.TestCase):
    def test_single_thread(self) -> None:
        text = (FIXTURES / "single-thread.txt").read_text()
        summary = parse_cyclictest_text(text)
        assert summary is not None
        self.assertEqual(summary.thread_count, 1)
        self.assertEqual(summary.overall_min_us, 4)
        self.assertEqual(summary.overall_max_us, 365)
        self.assertEqual(summary.rounded_avg_us(), 5)
        self.assertEqual(summary.sched_policy, "SCHED_FIFO")
        self.assertEqual(summary.sched_priority, 80)
        self.assertEqual(summary.scheduling_threshold_assessment(), "under")

    def test_multi_thread_aggregates_all_workers(self) -> None:
        text = (FIXTURES / "multi-thread.txt").read_text()
        summary = parse_cyclictest_text(text)
        assert summary is not None
        self.assertEqual(summary.thread_count, 4)
        self.assertEqual(summary.overall_min_us, 2)
        self.assertEqual(summary.overall_max_us, 300)
        # weighted avg: (10+6+12+8)*100000 / 400000 = 9
        self.assertEqual(summary.rounded_avg_us(), 9)
        last_only_min = 5
        last_only_max = 100
        self.assertNotEqual(summary.overall_min_us, last_only_min)
        self.assertNotEqual(summary.overall_max_us, last_only_max)

    def test_no_summary_returns_none(self) -> None:
        text = (FIXTURES / "no-summary.txt").read_text()
        self.assertIsNone(parse_cyclictest_text(text))

    def test_loaded_2639_us_is_exceeded_never_under(self) -> None:
        """Retained 201201Z loaded max must render exceeded, never under."""
        text = (FIXTURES / "loaded-2639us.txt").read_text()
        summary = parse_cyclictest_text(text)
        assert summary is not None
        self.assertEqual(summary.overall_max_us, 2639)
        self.assertGreater(summary.overall_max_us, HOST_RISK_THRESHOLD_US)
        self.assertEqual(summary.scheduling_threshold_assessment(), "exceeded")
        data = summary_to_dict(summary)
        self.assertEqual(data["scheduling_threshold_assessment"], "exceeded")
        self.assertFalse(data["wire_timing_measured"])
        self.assertEqual(data["clause9_conformance"], "not_claimed")
        section = "\n".join(format_result_section("cyclictest-loaded.txt", summary))
        self.assertIn("**exceeded**", section)
        self.assertNotIn("**under**", section)

    def test_idle_239_us_is_under(self) -> None:
        text = (FIXTURES / "idle-239us.txt").read_text()
        summary = parse_cyclictest_text(text)
        assert summary is not None
        self.assertEqual(summary.overall_max_us, 239)
        self.assertEqual(summary.scheduling_threshold_assessment(), "under")


if __name__ == "__main__":
    unittest.main()
