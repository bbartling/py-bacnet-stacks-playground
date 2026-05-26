"""Edge MQTT payload helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aws_iot_publisher import EdgeMqttConfig
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

    def test_edge_config_builds_two_messages(self) -> None:
        cfg = EdgeMqttConfig(
            site_id="demo",
            building_id="bens-office",
            system_id="office",
            point_deg_c="digital-temp-degC",
            point_deg_f="digital-temp-degF",
            brick_tag="BenOffice-ZAT",
        )
        msgs = cfg.build_messages(21.0, 69.8, seq=1)
        self.assertEqual(len(msgs), 2)
        self.assertTrue(msgs[0][0].endswith("/digital-temp-degC/telemetry"))
        self.assertTrue(msgs[1][0].endswith("/digital-temp-degF/telemetry"))


if __name__ == "__main__":
    unittest.main()
