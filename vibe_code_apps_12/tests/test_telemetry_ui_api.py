"""Tests for telemetry freshness and deployment helpers."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
sys.path.insert(0, str(ROOT))

from telemetry_api import (  # noqa: E402
    FRESH_GREEN_MAX_MIN,
    _series_point_metadata,
    deployment_readiness,
    ingest_freshness,
)


class TestSeriesPointMetadata(unittest.TestCase):
    def test_registry_fields_used(self) -> None:
        meta = _series_point_metadata(
            {
                "brick_class": "Zone_Air_Temperature_Sensor",
                "brick_tag": "STAT-ZN-T",
                "object_name": "STAT ZN-T",
            },
            None,
        )
        self.assertEqual(meta["object_name"], "STAT ZN-T")
        self.assertEqual(meta["brick_class"], "Zone_Air_Temperature_Sensor")

    def test_falls_back_to_latest_sample(self) -> None:
        meta = _series_point_metadata(
            {"brick_class": ""},
            {"object_name": "OA-H", "brick_class": "Outside_Air_Humidity_Sensor"},
        )
        self.assertEqual(meta["object_name"], "OA-H")
        self.assertEqual(meta["brick_class"], "Outside_Air_Humidity_Sensor")


class TestIngestFreshness(unittest.TestCase):
    def test_offline_when_no_timestamp(self):
        f = ingest_freshness(0, now_ms=1_000_000_000_000)
        self.assertEqual(f["status"], "offline")

    def test_green_under_20_min(self):
        now = 1_000_000_000_000
        f = ingest_freshness(now - 10 * 60 * 1000, now_ms=now)
        self.assertEqual(f["status"], "green")

    def test_yellow_band(self):
        now = 1_000_000_000_000
        f = ingest_freshness(now - 25 * 60 * 1000, now_ms=now)
        self.assertEqual(f["status"], "yellow")

    def test_orange_band(self):
        now = 1_000_000_000_000
        f = ingest_freshness(now - 50 * 60 * 1000, now_ms=now)
        self.assertEqual(f["status"], "orange")

    def test_red_over_hour(self):
        now = 1_000_000_000_000
        f = ingest_freshness(now - 90 * 60 * 1000, now_ms=now)
        self.assertEqual(f["status"], "red")

    def test_threshold_constants(self):
        self.assertEqual(FRESH_GREEN_MAX_MIN, 20)


class TestDeploymentReadiness(unittest.TestCase):
    def test_empty_store_not_ready(self):
        store = MagicMock()
        store.list_buildings.return_value = []
        out = deployment_readiness(store)
        self.assertFalse(out["ready"])
        self.assertTrue(any(c["id"] == "sites" and not c["ok"] for c in out["checks"]))


if __name__ == "__main__":
    unittest.main()
