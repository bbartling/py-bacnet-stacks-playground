"""Ingest Lambda batch telemetry handler."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[1]
_INGEST = _ROOT / "aws_cloud_pipeline" / "ingest_lambda"


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
    ingest_path = str(_INGEST)
    if ingest_path in sys.path:
        sys.path.remove(ingest_path)
    sys.path.insert(0, ingest_path)
    spec = importlib.util.spec_from_file_location(
        "vibe12_ingest_lambda", _INGEST / "lambda_function.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod, table


class TestIngestBatch(unittest.TestCase):
    def test_batch_ingests_multiple_samples(self) -> None:
        ingest, table = _load_ingest_lambda()
        event = {
            "source": "bacnet_batch",
            "site_id": "demo",
            "building_id": "bens-office",
            "seq": 1,
            "ts_ms": 1_700_000_000_000,
            "sample_count": 2,
            "mqtt_topic": "vibe12/demo/bens-office/batch/telemetry",
            "samples": [
                {
                    "source": "bacnet",
                    "site_id": "demo",
                    "building_id": "bens-office",
                    "system_id": "bens-test-bench-box",
                    "point_id": "5007-analog-input-1168",
                    "series_id": "demo#bens-office#bens-test-bench-box#5007-analog-input-1168",
                    "value": 42.0,
                    "unit": "percent-relative-humidity",
                    "ts_ms": 1_700_000_000_000,
                },
                {
                    "source": "bacnet",
                    "site_id": "demo",
                    "building_id": "bens-office",
                    "system_id": "bens-test-bench-box",
                    "point_id": "5007-analog-input-10014",
                    "series_id": "demo#bens-office#bens-test-bench-box#5007-analog-input-10014",
                    "value": 72.0,
                    "unit": "degrees-fahrenheit",
                    "ts_ms": 1_700_000_000_000,
                },
            ],
        }
        with patch.object(ingest, "_upsert_point_registry"):
            result = ingest.lambda_handler(event, None)
        self.assertEqual(result["mode"], "batch")
        self.assertEqual(result["ingested"], 2)
        self.assertGreaterEqual(table.put_item.call_count, 2)


if __name__ == "__main__":
    unittest.main()
