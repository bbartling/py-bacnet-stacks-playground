"""Tests for Vibe12 Open-FDD PyPI cloud demo rule pack."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import pyarrow as pa

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
_FDD = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "fdd_lambda"
for p in (_WEB, _FDD):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from brick_fdd_runner import run_brick_scoped_rules  # noqa: E402
from model_store import load_demo_canonical_model  # noqa: E402
from open_fdd.arrow_runtime import run_arrow_rule  # noqa: E402
from rules_defaults import (  # noqa: E402
    DEFAULT_FAULT_RULE_PACK,
    default_custom_rules,
)


def _synthetic_temp_table(n: int = 24, base: float = 72.0, spike: float = 85.0) -> pa.Table:
    temps = [base] * (n - 3) + [spike, spike, spike]
    ts_ms = [i * 60_000 for i in range(n)]
    return pa.table({"ts_ms": ts_ms, "temp": temps, "degF": temps, "value": temps})


def _synthetic_humidity_table(n: int = 12) -> pa.Table:
    vals = [50.0] * 8 + [90.0] * 4
    return pa.table({"ts_ms": list(range(n)), "value": vals, "temp": vals})


class TestRequirementsPin(unittest.TestCase):
    def test_fdd_requirements_pins_open_fdd(self) -> None:
        req = (_FDD / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"open-fdd==3\.0\.\d+")
        self.assertNotIn("pandas", req.lower())


class TestDemoRulesPack(unittest.TestCase):
    def test_default_pack_has_five_rules(self) -> None:
        rules = default_custom_rules()
        self.assertEqual(len(rules), 5)
        self.assertEqual(DEFAULT_FAULT_RULE_PACK, "vibe12_openfdd_cloud_demo_v1")
        ids = {r["id"] for r in rules}
        self.assertEqual(
            ids,
            {
                "demo_zone_temp_oob",
                "demo_outside_humidity_oob",
                "demo_duct_zone_delta",
                "demo_duct_outside_sanity",
                "demo_numpy_zone_temp_slope",
            },
        )

    def test_rules_use_arrow_contract(self) -> None:
        for rule in default_custom_rules():
            self.assertEqual(rule.get("backend"), "arrow")
            self.assertIn("apply_faults_arrow", rule.get("code") or "")
            self.assertNotRegex(rule.get("code") or "", r"def evaluate\(row")
            self.assertTrue(rule.get("brick_scope"))
            self.assertIsInstance(rule.get("config"), dict)

    def test_zone_oob_flags_high_temp(self) -> None:
        rule = next(r for r in default_custom_rules() if r["id"] == "demo_zone_temp_oob")
        result = run_arrow_rule(rule["code"], _synthetic_temp_table(), rule["config"], rule_id=rule["id"])
        self.assertFalse(result.errors, msg=str(result.errors))
        self.assertGreater(sum(result.fault_mask.to_pylist()), 0)

    def test_humidity_oob_flags(self) -> None:
        rule = next(r for r in default_custom_rules() if r["id"] == "demo_outside_humidity_oob")
        result = run_arrow_rule(rule["code"], _synthetic_humidity_table(), rule["config"], rule_id=rule["id"])
        self.assertFalse(result.errors)
        self.assertGreater(sum(result.fault_mask.to_pylist()), 0)

    def test_numpy_rule_returns_arrow_mask(self) -> None:
        from brick_fdd_runner import _run_numpy_demo_rule

        rule = next(r for r in default_custom_rules() if r["id"] == "demo_numpy_zone_temp_slope")
        n = 20
        temps = [70.0 + i * 0.8 for i in range(n)]
        table = pa.table({"ts_ms": list(range(n)), "temp": temps})
        mask, errors = _run_numpy_demo_rule(rule["code"], table, rule["config"], rule["id"])
        self.assertEqual(errors, [])
        py_mask = mask.to_pylist()
        self.assertEqual(len(py_mask), n)
        self.assertIsInstance(py_mask[0], bool)

    def test_numpy_rule_handles_nan(self) -> None:
        import math

        from brick_fdd_runner import _run_numpy_demo_rule

        rule = next(r for r in default_custom_rules() if r["id"] == "demo_numpy_zone_temp_slope")
        temps = [70.0, math.nan, 71.0, 72.5, 74.0, 76.0]
        table = pa.table({"ts_ms": list(range(len(temps))), "temp": temps})
        mask, errors = _run_numpy_demo_rule(rule["code"], table, rule["config"], rule["id"])
        self.assertEqual(errors, [])
        self.assertEqual(len(mask), len(temps))


class TestDemoCanonicalModel(unittest.TestCase):
    def test_demo_model_loads(self) -> None:
        model = load_demo_canonical_model("demo", "bens-office")
        self.assertIsNotNone(model)
        assert model is not None
        ext_ids = {p.get("external_id") for p in model.get("points", [])}
        self.assertEqual(ext_ids, {"OA-H", "OA-T", "DUCT-T", "STAT-ZN-T"})
        meta = (model.get("sites") or [{}])[0].get("metadata") or {}
        self.assertEqual(meta.get("bacnet_device"), 5007)

    def test_brick_targets_expand(self) -> None:
        from unittest.mock import MagicMock

        model = load_demo_canonical_model("demo", "bens-office")
        assert model is not None
        readings = [{"ts_ms": i * 60_000, "degF": 90.0, "ts": ""} for i in range(5)]
        store = MagicMock()
        store.list_points.return_value = [
            {"series_id": "demo#bens-office#bench-1#STAT-ZN-T", "brick_class": "Zone_Air_Temperature_Sensor"}
        ]
        store.get_multi_series.return_value = {
            "demo#bens-office#bench-1#STAT-ZN-T": readings,
        }
        rules = [default_custom_rules()[0]]
        summary = run_brick_scoped_rules(model, rules, store, "demo", "bens-office", hours=2)
        self.assertEqual(summary["fdd_backend"], "arrow")
        self.assertIn("open_fdd_version", summary)
        self.assertIn("numpy_available", summary)
        self.assertGreaterEqual(summary["targets_evaluated"], 1)


class TestWebHealthContract(unittest.TestCase):
    def test_health_payload_uses_arrow_contract(self) -> None:
        import importlib

        loader = importlib.import_module("web_lambda_loader")
        mod = loader.load_web_lambda("vibe12_health_test")
        payload = mod._health_payload()
        self.assertEqual(payload.get("rule_contract"), "apply_faults_arrow(table, cfg, context=None)")
        self.assertIn("open_fdd_rule_cookbook", payload)
        self.assertNotIn("row_fields", payload)


if __name__ == "__main__":
    unittest.main()
