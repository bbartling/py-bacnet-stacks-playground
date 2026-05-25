"""Ingest Lambda writes BRICK fields on telemetry put_item."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_INGEST = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "ingest_lambda"


def _load_ingest_lambda():
    """Load ingest lambda_function with boto3 stubbed."""
    boto3 = MagicMock()
    table = MagicMock()
    boto3.resource.return_value.Table.return_value = table
    sys.modules["boto3"] = boto3
    for mod in list(sys.modules):
        if mod in (
            "mqtt_routing",
            "brick_timeseries",
            "lambda_function",
            "vibe12_ingest_lambda",
            "vibe12_ingest_mqtt_routing",
        ):
            del sys.modules[mod]
    if str(_INGEST) not in sys.path:
        sys.path.insert(0, str(_INGEST))
    spec = importlib.util.spec_from_file_location(
        "vibe12_ingest_lambda", _INGEST / "lambda_function.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod, table


class TestIngestTelemetryItem(unittest.TestCase):
    def test_put_telemetry_includes_brick_timeseries_ref(self) -> None:
        ingest, table = _load_ingest_lambda()
        body = {
            "source": "edge",
            "site_id": "demo",
            "building_id": "bens-office",
            "system_id": "office",
            "point_id": "digital-temp-degC",
            "series_id": "demo#bens-office#office#digital-temp-degC",
            "value": 21.5,
            "unit": "degreesCelsius",
            "brick_class": "Zone_Air_Temperature_Sensor",
            "brick_tag": "BenOffice-ZAT",
            "ts_ms": 1_700_000_000_000,
        }
        topic = "vibe12/demo/bens-office/office/digital-temp-degC/telemetry"

        with patch.object(ingest, "_upsert_point_registry"):
            result = ingest._put_telemetry(body, topic)

        self.assertTrue(result["ok"])
        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["external_ref"], body["series_id"])
        self.assertIn("entity_id", item)
        self.assertIn("brick_timeseries_ref", item)
        ref = json.loads(item["brick_timeseries_ref"])
        self.assertEqual(ref["external_ref"], body["series_id"])
        self.assertEqual(ref["brick_class"], "Zone_Air_Temperature_Sensor")

    def test_lambda_handler_edge_payload(self) -> None:
        ingest, table = _load_ingest_lambda()
        event = {
            "source": "bacnet",
            "site_id": "demo",
            "building_id": "bens-office",
            "system_id": "bench",
            "point_id": "5007-analog-input-10014",
            "series_id": "demo#bens-office#bench#5007-analog-input-10014",
            "value": 72.0,
            "unit": "degrees-fahrenheit",
            "mqtt_topic": "vibe12/demo/bens-office/bench/5007-analog-input-10014/telemetry",
            "ts_ms": 1_700_000_000_001,
        }
        with patch.object(ingest, "_upsert_point_registry"):
            result = ingest.lambda_handler(event, None)
        self.assertEqual(result["mode"], "telemetry")
        item = table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["source"], "bacnet")


if __name__ == "__main__":
    unittest.main()
