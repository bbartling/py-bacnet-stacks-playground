"""Default FDD rules — independent brick_scope per rule."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from rules_defaults import default_custom_rules  # noqa: E402


class TestRulesDefaults(unittest.TestCase):
    def test_brick_scope_not_shared(self) -> None:
        rules = default_custom_rules()
        self.assertEqual(len(rules), 5)
        a, b = rules[0]["brick_scope"], rules[1]["brick_scope"]
        self.assertIsNot(a, b)
        a["point_classes"].append("Test_Point")
        self.assertNotIn("Test_Point", b.get("point_classes", []))


if __name__ == "__main__":
    unittest.main()
