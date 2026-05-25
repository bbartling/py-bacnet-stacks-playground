"""BRICK scope picklists from registry + model."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from brick_scope_options import brick_scope_options  # noqa: E402


class TestBrickScopeOptions(unittest.TestCase):
    def test_registry_only(self) -> None:
        opts = brick_scope_options(
            [{"brick_class": "Zone_Air_Temperature_Sensor", "series_id": "a"}],
            None,
        )
        self.assertTrue(opts["has_data"])
        self.assertIn("Zone_Air_Temperature_Sensor", opts["points"])
        self.assertEqual(opts["registry_point_count"], 1)

    def test_empty(self) -> None:
        opts = brick_scope_options([], {})
        self.assertFalse(opts["has_data"])
        self.assertEqual(opts["equipment"], [])
        self.assertEqual(opts["points"], [])

    def test_model_equipment_type(self) -> None:
        opts = brick_scope_options(
            [],
            {"equipment": [{"equipment_type": "Air_Handling_Unit"}], "points": []},
        )
        self.assertIn("Air_Handling_Unit", opts["equipment"])


if __name__ == "__main__":
    unittest.main()
