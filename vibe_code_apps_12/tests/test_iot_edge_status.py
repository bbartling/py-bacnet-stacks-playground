"""Tests for optional AWS IoT Core edge connectivity polling."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
sys.path.insert(0, str(ROOT))

import iot_edge_status  # noqa: E402


class TestParseThingsConfig(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("IOT_EDGE_THINGS", None)
        iot_edge_status._THINGS_CACHE = None

    def test_empty_when_unset(self) -> None:
        os.environ.pop("IOT_EDGE_THINGS", None)
        self.assertEqual(iot_edge_status._parse_things_config(), [])

    def test_parses_valid_array(self) -> None:
        os.environ["IOT_EDGE_THINGS"] = json.dumps(
            [
                {
                    "site_id": "demo",
                    "building_id": "bens-office",
                    "thing_name": "bosspi",
                    "client_id": "basicPubSub",
                    "label": "Boss Pi",
                }
            ]
        )
        rows = iot_edge_status._parse_things_config()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["site_id"], "demo")
        self.assertEqual(rows[0]["client_id"], "basicPubSub")

    def test_skips_incomplete_rows(self) -> None:
        os.environ["IOT_EDGE_THINGS"] = json.dumps([{"site_id": "demo"}])
        self.assertEqual(iot_edge_status._parse_things_config(), [])

    def test_invalid_json_returns_empty(self) -> None:
        os.environ["IOT_EDGE_THINGS"] = "not-json"
        self.assertEqual(iot_edge_status._parse_things_config(), [])


class TestLookupIotEdgeThings(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("IOT_EDGE_THINGS", None)
        iot_edge_status._THINGS_CACHE = None

    def test_not_configured_hint(self) -> None:
        os.environ.pop("IOT_EDGE_THINGS", None)
        out = iot_edge_status.lookup_iot_edge_things(use_cache=False)
        self.assertFalse(out["configured"])
        self.assertIn("IOT_EDGE_THINGS", out["hint"])

    @patch.object(iot_edge_status, "_status_from_connectivity_api")
    def test_merges_connected_thing(self, mock_api: MagicMock) -> None:
        os.environ["IOT_EDGE_THINGS"] = json.dumps(
            [
                {
                    "site_id": "demo",
                    "building_id": "bens-office",
                    "thing_name": "bosspi",
                    "client_id": "basicPubSub",
                }
            ]
        )
        mock_api.return_value = {
            "thing_name": "bosspi",
            "connected": True,
            "source": "iot_get_thing_connectivity_data",
        }
        out = iot_edge_status.lookup_iot_edge_things(use_cache=False)
        self.assertTrue(out["configured"])
        self.assertEqual(out["things"][0]["mqtt_connected"], True)
        self.assertEqual(out["things"][0]["mqtt_status"], "connected")


if __name__ == "__main__":
    unittest.main()
