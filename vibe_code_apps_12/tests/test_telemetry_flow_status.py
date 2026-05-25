"""telemetry_api flow + commissioning status (mocked DynamoDB)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"


def _install_boto3_stub() -> None:
    boto3 = MagicMock()
    dynamodb = ModuleType("boto3.dynamodb")
    dynamodb.conditions = ModuleType("boto3.dynamodb.conditions")  # type: ignore[attr-defined]
    dynamodb.conditions.Key = MagicMock(name="Key")  # type: ignore[attr-defined]
    boto3.dynamodb = dynamodb  # type: ignore[attr-defined]
    sys.modules["boto3"] = boto3
    sys.modules["boto3.dynamodb"] = dynamodb
    sys.modules["boto3.dynamodb.conditions"] = dynamodb.conditions


def _load_telemetry_api():
    _install_boto3_stub()
    if str(_WEB) not in sys.path:
        sys.path.insert(0, str(_WEB))
    for mod in (
        "brick_timeseries",
        "telemetry_api",
        "mqtt_routing",
        "vibe12_telemetry_api",
        "vibe12_ingest_lambda",
    ):
        sys.modules.pop(mod, None)
    spec = importlib.util.spec_from_file_location(
        "vibe12_telemetry_api", _WEB / "telemetry_api.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestTelemetryFlowStatus(unittest.TestCase):
    def setUp(self) -> None:
        self.api = _load_telemetry_api()

    def test_flowing_when_recent_sample(self) -> None:
        now_ms = int(time.time() * 1000)
        ref = self.api.brick_timeseries_ref(
            site_id="demo",
            building_id="bens-office",
            system_id="office",
            point_id="digital-temp-degC",
            series_id="demo#bens-office#office#digital-temp-degC",
            brick_class="Zone_Air_Temperature_Sensor",
            unit="degreesCelsius",
        )
        store = MagicMock()
        store.list_points.return_value = [
            {
                "series_id": "demo#bens-office#office#digital-temp-degC",
                "point_id": "digital-temp-degC",
                "system_id": "office",
                "brick_class": "Zone_Air_Temperature_Sensor",
                "brick_tag": "BenOffice-ZAT",
                "unit": "degreesCelsius",
                "brick_timeseries_ref": ref,
                "entity_id": ref["entity_id"],
            }
        ]
        store._table.query.return_value = {
            "Items": [
                {
                    "ts_ms": now_ms,
                    "value": 22.5,
                    "unit": "degreesCelsius",
                    "source": "edge",
                    "brick_timeseries_ref": json.dumps(ref),
                }
            ]
        }

        out = self.api.telemetry_flow_status(
            store, "demo", "bens-office", window_minutes=15
        )
        self.assertTrue(out["cloud_ingest_ok"])
        self.assertEqual(out["series_flowing"], 1)
        self.assertEqual(out["series_total"], 1)
        self.assertEqual(out["points_registered"], 1)
        self.assertTrue(out["series"][0]["flowing"])

    def test_not_flowing_when_stale(self) -> None:
        old_ms = int(time.time() * 1000) - 3600_000
        store = MagicMock()
        store.list_points.return_value = [
            {
                "series_id": "demo#bens-office#office#digital-temp-degC",
                "point_id": "digital-temp-degC",
                "system_id": "office",
            }
        ]
        store._table.query.return_value = {
            "Items": [{"ts_ms": old_ms, "value": 20.0, "source": "edge"}]
        }

        out = self.api.telemetry_flow_status(
            store, "demo", "bens-office", window_minutes=15
        )
        self.assertFalse(out["cloud_ingest_ok"])
        self.assertEqual(out["series_flowing"], 0)

    def test_commissioning_recommends_fix_when_empty_registry(self) -> None:
        store = MagicMock()
        store.list_points.return_value = []
        out = self.api.commissioning_status(store, "demo", "bens-office")
        self.assertFalse(out["cloud_ingest_ok"])
        self.assertIn("ai_hints", out)
        actions = " ".join(out.get("recommended_actions", []))
        self.assertIn("registry", actions.lower())


if __name__ == "__main__":
    unittest.main()
