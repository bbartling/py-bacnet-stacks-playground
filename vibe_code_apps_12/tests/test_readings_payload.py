"""Regression tests for /api/readings payload assembly (no AWS)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from rules_defaults import default_custom_rules  # noqa: E402
from web_lambda_loader import load_web_lambda  # noqa: E402

lambda_function = load_web_lambda("vibe12_web_lambda_function")


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
    @unittest.mock.patch.object(lambda_function, "_fetch_fdd_status")
    @unittest.mock.patch.object(lambda_function, "_fetch_readings")
    @unittest.mock.patch.object(lambda_function, "_load_custom_rules")
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

    @unittest.mock.patch.object(lambda_function, "_fetch_fdd_status")
    @unittest.mock.patch.object(lambda_function, "_fetch_readings")
    @unittest.mock.patch.object(lambda_function, "_load_custom_rules")
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
