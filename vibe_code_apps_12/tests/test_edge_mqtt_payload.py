"""Edge MQTT payload helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from edge_bacnet.mqtt_payload import build_edge_payload, mqtt_topic_for_ids


class TestEdgeMqttPayload(unittest.TestCase):
    def test_topic_and_payload(self) -> None:
        topic = mqtt_topic_for_ids("demo", "bens-office", "office", "digital-temp-degC")
        self.assertEqual(
            topic,
            "vibe12/demo/bens-office/office/digital-temp-degC/telemetry",
        )
        body = build_edge_payload(
            site_id="demo",
            building_id="bens-office",
            system_id="office",
            point_id="digital-temp-degC",
            value=21.5,
            unit="degreesCelsius",
            brick_class="Zone_Air_Temperature_Sensor",
            brick_tag="BenOffice-ZAT",
            object_name="Ben's office DS18B20 °C",
        )
        self.assertIn('"source": "edge"', body)
        self.assertIn("demo#bens-office#office#digital-temp-degC", body)
        self.assertIn("Ben's office DS18B20", body)
        self.assertIn("Zone_Air_Temperature_Sensor", body)

if __name__ == "__main__":
    unittest.main()
