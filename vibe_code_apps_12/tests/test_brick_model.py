"""Brick model helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from brick_model import (  # noqa: E402
    entities_by_brick_class,
    graph_from_csv_text,
    graph_from_point_registry,
)


class TestBrickModel(unittest.TestCase):
    def test_graph_from_points(self) -> None:
        points = [
            {
                "series_id": "acme#tower-a#ahu-1#sat",
                "system_id": "ahu-1",
                "brick_class": "Supply_Air_Temperature_Sensor",
                "brick_tag": "SAT",
                "unit": "degF",
                "object_name": "STAT ZN-T",
            }
        ]
        g = graph_from_point_registry("acme", "tower-a", points)
        self.assertEqual(len(g["entities"]), 3)
        sites = entities_by_brick_class(g, "Site")
        self.assertEqual(len(sites), 1)
        sensors = entities_by_brick_class(g, "Supply_Air_Temperature_Sensor")
        self.assertEqual(len(sensors), 1)
        self.assertEqual(sensors[0]["ext:series_id"], "acme#tower-a#ahu-1#sat")
        self.assertEqual(sensors[0]["ext:object_name"], "STAT ZN-T")
        self.assertIn(
            {"subject": "brick:acme_tower-a_site", "predicate": "hasPart", "object": "brick:acme_tower-a_ahu-1"},
            g["relationships"],
        )
        self.assertIn(
            {"subject": "brick:acme_tower-a_ahu-1", "predicate": "isPartOf", "object": "brick:acme_tower-a_site"},
            g["relationships"],
        )
        self.assertIn(
            {"subject": "brick:acme_tower-a_SAT", "predicate": "isPartOf", "object": "brick:acme_tower-a_site"},
            g["relationships"],
        )

    def test_graph_from_csv(self) -> None:
        csv_text = (
            "device_instance,device_address,object_type,object_instance,"
            "object_name,description,present_value,units,site_id,building_id,"
            "system_id,brick_class,brick_tag,enabled,poll_interval_s,point_id,series_id\n"
            "3456788,192.168.1.10,analog-input,1,SAT,,72,degF,acme,tower-a,"
            "ahu-1,Supply_Air_Temperature_Sensor,SAT,1,,3456788-ai-1,\n"
        )
        g = graph_from_csv_text(csv_text, "acme", "tower-a")
        pts = entities_by_brick_class(g, "Supply_Air_Temperature_Sensor")
        self.assertEqual(len(pts), 1)


if __name__ == "__main__":
    unittest.main()
