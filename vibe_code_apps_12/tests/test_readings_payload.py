"""Regression tests for /api/readings payload assembly (no AWS)."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

with patch("boto3.resource") as _mock_boto:
    _mock_boto.return_value.Table.return_value = MagicMock()
    for mod in list(sys.modules):
        if mod in ("mqtt_routing", "lambda_function", "timeseries", "brick_model"):
            del sys.modules[mod]
    _spec = importlib.util.spec_from_file_location(
        "vibe12_web_lambda_function", _WEB / "lambda_function.py"
    )
    lambda_function = importlib.util.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(lambda_function)

from rules_defaults import default_custom_rules  # noqa: E402


def _sample_readings(n: int = 12, step_ms: int = 60_000) -> list[dict]:
    base = 1_700_000_000_000
    out = [
        {"ts_ms": base + i * step_ms, "degF": 70.0, "degC": 21.1}
        for i in range(n)
    ]
    out[-1]["degF"] = 90.0
    out[-1]["degC"] = 32.2
    return out


class TestReadingsPayload(unittest.TestCase):
    @patch.object(lambda_function, "_fetch_fdd_status")
    @patch.object(lambda_function, "_fetch_readings")
    @patch.object(lambda_function, "_load_custom_rules")
    def test_includes_fault_analytics(
        self,
        mock_rules,
        mock_readings,
        mock_fdd,
    ) -> None:
        rules = default_custom_rules()[:1]
        mock_rules.return_value = rules
        mock_readings.return_value = _sample_readings()
        mock_fdd.return_value = {"fdd_status": "NORMAL", "eval_log": []}

        payload = lambda_function._readings_payload(2, rolling_avg_minutes=1)

        self.assertIn("fault_analytics", payload)
        self.assertIn("fault_totals", payload)
        self.assertIsInstance(payload["fault_analytics"], list)
        self.assertGreaterEqual(len(payload["fault_analytics"]), 1)
        item = payload["fault_analytics"][0]
        self.assertIn("id", item)
        self.assertIn("count", item)
        self.assertIn("elapsed_ms", item)
        rule_id = item["id"]
        self.assertEqual(item["count"], payload["fault_totals"].get(rule_id, 0))

    @patch.object(lambda_function, "_fetch_fdd_status")
    @patch.object(lambda_function, "_fetch_readings")
    @patch.object(lambda_function, "_load_custom_rules")
    def test_chunked_path_builds_fault_analytics(
        self,
        mock_rules,
        mock_readings,
        mock_fdd,
    ) -> None:
        rules = default_custom_rules()[:1]
        mock_rules.return_value = rules
        # Enough samples to trigger chunked eval (CHART_CHUNKED_SAMPLES default 8000)
        mock_readings.return_value = _sample_readings(8100, step_ms=10_000)
        mock_fdd.return_value = {"fdd_status": "PENDING", "eval_log": []}

        payload = lambda_function._readings_payload(24, rolling_avg_minutes=1)

        self.assertTrue(payload["chart_eval_chunked"])
        self.assertIn("fault_analytics", payload)
        self.assertEqual(len(payload["fault_analytics"]), 1)


if __name__ == "__main__":
    unittest.main()
