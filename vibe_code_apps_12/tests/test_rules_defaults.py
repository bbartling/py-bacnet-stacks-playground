"""Tests for rules_defaults helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from rules_defaults import chart_guides_from_rules, default_custom_rules, rules_meta  # noqa: E402


class TestRulesMeta(unittest.TestCase):
    def test_default_rules_have_plot_on_chart(self) -> None:
        rules = default_custom_rules()
        self.assertGreaterEqual(len(rules), 4)
        for r in rules:
            self.assertIn("plot_on_chart", r)

    def test_rules_meta_shape(self) -> None:
        rules = default_custom_rules()
        meta = rules_meta(rules)
        self.assertEqual(len(meta), len(rules))
        self.assertIn("enabled", meta[0])
        self.assertIn("plot_on_chart", meta[0])

    def test_chart_guides_from_bounds_rule(self) -> None:
        rules = default_custom_rules()
        guides = chart_guides_from_rules(rules)
        self.assertEqual(guides["bounds_low"], 65.0)
        self.assertEqual(guides["bounds_high"], 80.0)
        guides_c = chart_guides_from_rules(rules, "metric")
        self.assertEqual(guides_c["temp_unit"], "metric")


if __name__ == "__main__":
    unittest.main()
