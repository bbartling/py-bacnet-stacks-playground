"""Dynamo time-series building registry scans."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"


def _load_timeseries():
    boto3 = ModuleType("boto3")
    dynamodb = ModuleType("boto3.dynamodb")
    dynamodb.conditions = ModuleType("boto3.dynamodb.conditions")  # type: ignore[attr-defined]
    dynamodb.conditions.Key = MagicMock(name="Key")  # type: ignore[attr-defined]
    sys.modules["boto3"] = boto3
    sys.modules["boto3.dynamodb"] = dynamodb
    sys.modules["boto3.dynamodb.conditions"] = dynamodb.conditions
    if str(_WEB) not in sys.path:
        sys.path.insert(0, str(_WEB))
    for mod in ("mqtt_routing", "timeseries", "vibe12_timeseries"):
        sys.modules.pop(mod, None)
    spec = importlib.util.spec_from_file_location("vibe12_timeseries", _WEB / "timeseries.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestListBuildings(unittest.TestCase):
    def test_paginates_past_empty_filtered_scan_page(self) -> None:
        ts = _load_timeseries()
        table = MagicMock()
        table.scan.side_effect = [
            {"Items": [], "LastEvaluatedKey": {"device_id": "some-series", "ts_ms": 1}},
            {
                "Items": [
                    {
                        "device_id": "meta#demo#bens-office",
                        "ts_ms": -11,
                        "site_id": "demo",
                        "building_id": "bens-office",
                    }
                ]
            },
        ]

        buildings = ts.DynamoTimeSeriesStore(table).list_buildings()

        self.assertEqual(
            buildings,
            [
                {
                    "site_id": "demo",
                    "building_id": "bens-office",
                    "building_scope": "demo#bens-office",
                }
            ],
        )
        self.assertEqual(table.scan.call_count, 2)
        self.assertIn("ExclusiveStartKey", table.scan.call_args_list[1].kwargs)


if __name__ == "__main__":
    unittest.main()
