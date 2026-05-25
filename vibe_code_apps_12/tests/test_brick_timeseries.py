"""BRICK time-series ref helpers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_INGEST = _ROOT / "aws_cloud_pipeline" / "ingest_lambda"
if str(_INGEST) not in sys.path:
    sys.path.insert(0, str(_INGEST))

from brick_timeseries import brick_timeseries_ref, registry_entry_from_row  # noqa: E402


class TestBrickTimeseries(unittest.TestCase):
    def test_ref_maps_dynamodb_external_ref(self):
        ref = brick_timeseries_ref(
            site_id="demo",
            building_id="bens-office",
            system_id="office",
            point_id="digital-temp-degC",
            series_id="demo#bens-office#office#digital-temp-degC",
            brick_class="Zone_Air_Temperature_Sensor",
            brick_tag="BenOffice-ZAT",
        )
        self.assertEqual(ref["external_ref"], "demo#bens-office#office#digital-temp-degC")
        self.assertEqual(
            ref["dynamodb"]["table_key"]["device_id"],
            "demo#bens-office#office#digital-temp-degC",
        )
        self.assertIn("vibe12/demo/bens-office/office/digital-temp-degC/telemetry", ref["mqtt_topic"])

    def test_registry_entry_roundtrip(self):
        row = {
            "site_id": "demo",
            "building_id": "bens-office",
            "system_id": "bens-test-bench-box",
            "point_id": "5007-analog-input-10014",
            "series_id": "demo#bens-office#bens-test-bench-box#5007-analog-input-10014",
            "unit": "degreesFahrenheit",
            "brick_class": "Zone_Air_Temperature_Sensor",
            "brick_tag": "STAT-ZN-T",
            "object_name": "STAT ZN-T",
            "source": "bacnet",
            "equipment_type": "HVAC_Equipment",
        }
        entry = registry_entry_from_row(row)
        self.assertEqual(entry["external_ref"], row["series_id"])
        self.assertEqual(entry["brick_timeseries_ref"]["entity_id"], entry["entity_id"])
        json.dumps(entry["brick_timeseries_ref"])


if __name__ == "__main__":
    unittest.main()
