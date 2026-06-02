"""Batch MQTT payload builder."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from edge_bacnet.config import PointConfig
from edge_bacnet.mqtt_payload import (
    bacnet_sample_dict,
    build_bacnet_batch_payload,
    mqtt_batch_topic,
)


def _point(point_id: str) -> PointConfig:
    return PointConfig(
        device_instance=5007,
        device_address="2000:7@192.168.204.200",
        object_type="analog-input",
        object_instance=10014,
        object_name="STAT ZN-T",
        description="",
        units="degrees-fahrenheit",
        site_id="demo",
        building_id="bens-office",
        system_id="bens-test-bench-box",
        brick_class="Zone_Air_Temperature_Sensor",
        brick_tag="STAT-ZN-T",
        poll_interval_s=0,
        point_id=point_id,
        series_id=f"demo#bens-office#bens-test-bench-box#{point_id}",
        object_id="analog-input,10014",
    )


class TestBatchMqttPayload(unittest.TestCase):
    def test_batch_topic(self) -> None:
        self.assertEqual(
            mqtt_batch_topic("demo", "bens-office"),
            "vibe12/demo/bens-office/batch/telemetry",
        )

    def test_batch_payload_shape(self) -> None:
        pt = _point("5007-analog-input-10014")
        sample = bacnet_sample_dict(pt, 72.5, seq=1, ts_ms=1_700_000_000_000)
        raw = build_bacnet_batch_payload(
            [sample],
            site_id="demo",
            building_id="bens-office",
            seq=1,
            ts_ms=1_700_000_000_000,
        )
        body = json.loads(raw)
        self.assertEqual(body["source"], "bacnet_batch")
        self.assertEqual(body["sample_count"], 1)
        self.assertEqual(body["samples"][0]["value"], 72.5)
        self.assertEqual(body["site_id"], "demo")


if __name__ == "__main__":
    unittest.main()
