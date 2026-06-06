"""Brick FDD runner with mocked time series (Arrow-only)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from arrow_rules import ARROW_OOB  # noqa: E402
from brick_fdd_runner import run_brick_scoped_rules  # noqa: E402
from rules_defaults import default_custom_rules  # noqa: E402


class TestBrickFddRunner(unittest.TestCase):
    def test_arrow_oob_rule(self) -> None:
        model = {
            "sites": [{"id": "demo", "name": "Demo"}],
            "equipment": [
                {"id": "eq1", "site_id": "demo", "equipment_type": "Variable_Air_Volume_Box", "name": "vav-1"}
            ],
            "points": [
                {
                    "id": "pt1",
                    "site_id": "demo",
                    "equipment_id": "eq1",
                    "brick_type": "Zone_Air_Temperature_Sensor",
                    "external_id": "ZAT",
                    "metadata": {"external_ref": "demo#pi#vav-1#zat"},
                }
            ],
        }
        readings = [
            {"ts_ms": i * 60_000, "value": 90.0 if i > 2 else 70.0, "ts": ""}
            for i in range(5)
        ]
        store = MagicMock()
        store.list_points.return_value = [{"series_id": "demo#pi#vav-1#zat"}]
        store.get_multi_series.return_value = {"demo#pi#vav-1#zat": readings}

        rules = [
            {
                "id": "oob",
                "enabled": True,
                "brick_scope": {
                    "equipment_classes": ["Variable_Air_Volume_Box"],
                    "point_classes": ["Zone_Air_Temperature_Sensor"],
                },
                "config": {"bounds_high": 80.0, "bounds_low": 65.0, "rolling_avg_minutes": 1},
                "code": ARROW_OOB,
            }
        ]
        summary = run_brick_scoped_rules(model, rules, store, "demo", "pi", hours=2)
        self.assertEqual(summary["targets_evaluated"], 1)
        self.assertGreater(summary["total_flagged"], 0)
        self.assertEqual(summary["open_fdd_version"], "3.0.1")
        self.assertEqual(summary["results"][0]["backend"], "arrow")

    def test_arrow_default_oob_rule(self) -> None:
        model = {
            "sites": [{"id": "demo", "name": "Demo"}],
            "equipment": [
                {"id": "eq1", "site_id": "demo", "equipment_type": "Variable_Air_Volume_Box", "name": "vav-1"}
            ],
            "points": [
                {
                    "id": "pt1",
                    "site_id": "demo",
                    "equipment_id": "eq1",
                    "brick_type": "Zone_Air_Temperature_Sensor",
                    "external_id": "ZAT",
                    "metadata": {"external_ref": "demo#pi#vav-1#zat"},
                }
            ],
        }
        readings = [
            {"ts_ms": i * 60_000, "degF": 90.0 if i > 2 else 70.0, "ts": ""}
            for i in range(5)
        ]
        store = MagicMock()
        store.list_points.return_value = [{"series_id": "demo#pi#vav-1#zat"}]
        store.get_multi_series.return_value = {"demo#pi#vav-1#zat": readings}

        rules = [default_custom_rules()[0]]
        summary = run_brick_scoped_rules(model, rules, store, "demo", "pi", hours=2)
        self.assertEqual(summary["fdd_backend"], "arrow")
        self.assertGreater(summary["total_flagged"], 0)
        self.assertEqual(summary["results"][0]["backend"], "arrow")


if __name__ == "__main__":
    unittest.main()
