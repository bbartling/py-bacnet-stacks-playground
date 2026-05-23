"""Custom rules draft persistence (DynamoDB ts_ms=-2)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

with patch("boto3.resource") as _mock_boto:
    _mock_boto.return_value.Table.return_value = MagicMock()
    _spec = importlib.util.spec_from_file_location(
        "vibe12_web_lambda_rules", _WEB / "lambda_function.py"
    )
    lf = importlib.util.module_from_spec(_spec)
    assert _spec.loader is not None
    for mod in list(sys.modules):
        if mod in ("mqtt_routing", "lambda_function", "timeseries", "brick_model"):
            del sys.modules[mod]
    _spec.loader.exec_module(lf)


class TestRulesDraftPersistence(unittest.TestCase):
    def setUp(self) -> None:
        lf._table.put_item.reset_mock()
        lf._table.get_item.reset_mock()
        self.saved: dict = {}

        def _put(**kwargs):
            self.saved = kwargs.get("Item") or {}

        def _get(**kwargs):
            key = kwargs.get("Key") or {}
            if key.get("ts_ms") == lf.FDD_CUSTOM_RULES_TS and self.saved:
                return {"Item": self.saved}
            return {}

        lf._table.put_item.side_effect = _put
        lf._table.get_item.side_effect = _get

    def test_save_and_reload_preserves_titles(self) -> None:
        rules = [
            {
                "id": "rule_a",
                "title": "My custom OOB",
                "enabled": True,
                "config": {},
                "code": "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n",
            }
        ]
        updated = lf._save_custom_rules(rules)
        self.assertGreater(updated, 0)

        loaded, source, ts = lf._load_custom_rules_record()
        self.assertEqual(source, "dynamodb")
        self.assertEqual(loaded[0]["title"], "My custom OOB")
        self.assertEqual(ts, updated)

    def test_missing_draft_falls_back_to_defaults(self) -> None:
        loaded, source, ts = lf._load_custom_rules_record()
        self.assertEqual(source, "defaults")
        self.assertIsNone(ts)
        self.assertGreaterEqual(len(loaded), 1)


if __name__ == "__main__":
    unittest.main()
