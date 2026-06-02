"""MQTT topic routing for BACnet ingest."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_INGEST = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "ingest_lambda"
if str(_INGEST) not in sys.path:
    sys.path.insert(0, str(_INGEST))
for mod in list(sys.modules):
    if mod == "mqtt_routing":
        del sys.modules[mod]

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "vibe12_ingest_mqtt_routing", _INGEST / "mqtt_routing.py"
)
mqtt_routing = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(mqtt_routing)

parse_mqtt_topic = mqtt_routing.parse_mqtt_topic
parse_batch_topic = mqtt_routing.parse_batch_topic
is_batch_telemetry = mqtt_routing.is_batch_telemetry
building_scope = mqtt_routing.building_scope
is_bacnet_telemetry = mqtt_routing.is_bacnet_telemetry
is_series_telemetry = mqtt_routing.is_series_telemetry
series_row_from_bacnet = mqtt_routing.series_row_from_bacnet


class TestMqttTopicParse(unittest.TestCase):
    def test_parse_hierarchical_topic(self) -> None:
        t = "vibe12/acme/tower-a/ahu-1/3456788-analog-input-1/telemetry"
        meta = parse_mqtt_topic(t)
        self.assertEqual(meta["site"], "acme")
        self.assertEqual(meta["building"], "tower-a")
        self.assertEqual(meta["system"], "ahu-1")
        self.assertEqual(meta["point"], "3456788-analog-input-1")

    def test_rejects_flat_legacy_topic(self) -> None:
        self.assertIsNone(parse_mqtt_topic("sdk/test/python"))

    def test_parse_batch_topic(self) -> None:
        t = "vibe12/demo/bens-office/batch/telemetry"
        meta = parse_batch_topic(t)
        self.assertEqual(meta["site"], "demo")
        self.assertEqual(meta["building"], "bens-office")
        body = {"source": "bacnet_batch", "samples": [{"value": 1.0}]}
        self.assertTrue(is_batch_telemetry(body))

    def test_bacnet_series_row(self) -> None:
        body = {
            "source": "bacnet",
            "site_id": "acme",
            "building_id": "tower-a",
            "system_id": "ahu-1",
            "point_id": "3456788-ai-1",
            "series_id": "acme#tower-a#ahu-1#3456788-ai-1",
            "value": 72.5,
            "ts_ms": 1000,
        }
        row = series_row_from_bacnet(body, None)
        self.assertEqual(row["series_id"], "acme#tower-a#ahu-1#3456788-ai-1")
        self.assertEqual(row["building_scope"], building_scope("acme", "tower-a"))
        self.assertTrue(is_bacnet_telemetry(body))
        self.assertTrue(is_series_telemetry(body))

    def test_edge_series_telemetry(self) -> None:
        body = {
            "source": "edge",
            "site_id": "bens-cx",
            "building_id": "hospital-north",
            "system_id": "ahu-1",
            "point_id": "sat-degF",
            "series_id": "bens-cx#hospital-north#ahu-1#sat-degF",
            "value": 72.5,
            "ts_ms": 1000,
        }
        self.assertTrue(is_series_telemetry(body))
        self.assertFalse(is_bacnet_telemetry(body))


if __name__ == "__main__":
    unittest.main()
