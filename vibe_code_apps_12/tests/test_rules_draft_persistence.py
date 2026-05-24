"""Custom rules draft persistence (DynamoDB ts_ms=-2)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")

from web_lambda_loader import load_web_lambda  # noqa: E402

lf = load_web_lambda("vibe12_web_lambda_rules")


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
