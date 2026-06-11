"""Pydantic model schema validation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

from model_schema import normalize_model_payload, validate_model  # noqa: E402
from ttl_service import TtlService  # noqa: E402
from model_store import bootstrap_from_registry  # noqa: E402
from brick_rule_targets import expand_brick_targets  # noqa: E402
from assistant_import import extract_import_shape_from_llm_output  # noqa: E402


class TestModelSchema(unittest.TestCase):
    def test_validate_ok_model(self) -> None:
        payload = {
            "sites": [{"id": "demo", "name": "Demo"}],
            "equipment": [{"id": "eq1", "site_id": "demo", "equipment_type": "Air_Handling_Unit"}],
            "points": [
                {
                    "id": "pt1",
                    "site_id": "demo",
                    "equipment_id": "eq1",
                    "external_id": "SAT",
                    "object_name": "STAT ZN-T",
                    "brick_type": "Supply_Air_Temperature_Sensor",
                    "fdd_input": "Supply_Air_Temperature_Sensor",
                    "metadata": {"external_ref": "demo#pi#ahu-1#sat"},
                }
            ],
        }
        reg = {"demo#pi#ahu-1#sat"}
        out = validate_model(payload, registry_series_ids=reg)
        self.assertTrue(out["valid"])
        self.assertGreaterEqual(out["score"], 80)

    def test_orphan_point_fails(self) -> None:
        payload = {
            "sites": [{"id": "demo", "name": "Demo"}],
            "equipment": [],
            "points": [
                {
                    "id": "pt1",
                    "site_id": "demo",
                    "equipment_id": "missing",
                    "brick_type": "Sensor",
                    "metadata": {"external_ref": "x#y#z#p"},
                }
            ],
        }
        out = validate_model(payload)
        self.assertFalse(out["valid"])
        self.assertGreater(out["counts"]["orphan_points_equipment"], 0)


class TestTtlService(unittest.TestCase):
    def test_build_ttl_external_ref(self) -> None:
        model = {
            "sites": [
                {
                    "id": "demo",
                    "name": "Demo Site",
                    "metadata": {
                        "rule_pack": "brick_zone_temp_basic_v1",
                        "fault_rule": "brick_zone_oob",
                    },
                }
            ],
            "equipment": [
                {"id": "eq1", "site_id": "demo", "name": "AHU-1", "equipment_type": "Air_Handling_Unit"}
            ],
            "points": [
                {
                    "id": "pt1",
                    "site_id": "demo",
                    "equipment_id": "eq1",
                    "external_id": "SAT",
                    "object_name": "STAT ZN-T",
                    "brick_type": "Supply_Air_Temperature_Sensor",
                    "fdd_input": "Supply_Air_Temperature_Sensor",
                    "metadata": {"external_ref": "demo#pi#ahu-1#sat"},
                }
            ],
            "relationships": [],
        }
        ttl = TtlService().build_ttl(model)
        self.assertIn("vibe12:externalReference", ttl)
        self.assertIn("demo#pi#ahu-1#sat", ttl)
        self.assertIn("brick:Supply_Air_Temperature_Sensor", ttl)
        self.assertIn('rdfs:label "STAT ZN-T"', ttl)
        self.assertIn('vibe12:operatorTag "SAT"', ttl)
        self.assertIn('vibe12:objectName "STAT ZN-T"', ttl)
        self.assertIn('vibe12:faultRulePack "brick_zone_temp_basic_v1"', ttl)
        self.assertIn('vibe12:faultRule "brick_zone_oob"', ttl)


class TestBootstrap(unittest.TestCase):
    def test_registry_bootstrap(self) -> None:
        points = [
            {
                "system_id": "vav-1",
                "brick_tag": "ZAT",
                "brick_class": "Zone_Air_Temperature_Sensor",
                "series_id": "acme#tower#vav-1#zat",
                "unit": "degF",
                "object_name": "STAT ZN-T",
            }
        ]
        model = bootstrap_from_registry("acme", "tower", points)
        self.assertEqual(len(model["sites"]), 1)
        self.assertEqual(len(model["equipment"]), 1)
        self.assertEqual(len(model["points"]), 1)
        self.assertEqual(model["sites"][0]["metadata"]["rule_pack"], "vibe12_openfdd_cloud_demo_v1")
        self.assertEqual(model["sites"][0]["metadata"]["fault_rule"], "demo_zone_temp_oob")
        self.assertEqual(model["points"][0]["metadata"]["external_ref"], "acme#tower#vav-1#zat")
        self.assertEqual(model["points"][0]["object_name"], "STAT ZN-T")
        self.assertEqual(model["points"][0]["metadata"]["object_name"], "STAT ZN-T")


class TestBrickTargets(unittest.TestCase):
    def test_expand_vav_zat(self) -> None:
        model = {
            "sites": [{"id": "s1"}],
            "equipment": [
                {"id": "eq_vav", "site_id": "s1", "equipment_type": "Variable_Air_Volume_Box"},
                {"id": "eq_ahu", "site_id": "s1", "equipment_type": "Air_Handling_Unit"},
            ],
            "points": [
                {
                    "id": "p1",
                    "site_id": "s1",
                    "equipment_id": "eq_vav",
                    "brick_type": "Zone_Air_Temperature_Sensor",
                    "external_id": "ZAT1",
                    "metadata": {"external_ref": "s#b#vav#zat1"},
                },
                {
                    "id": "p2",
                    "site_id": "s1",
                    "equipment_id": "eq_ahu",
                    "brick_type": "Supply_Air_Temperature_Sensor",
                    "external_id": "SAT",
                    "metadata": {"external_ref": "s#b#ahu#sat"},
                },
            ],
        }
        scope = {
            "equipment_classes": ["Variable_Air_Volume_Box"],
            "point_classes": ["Zone_Air_Temperature_Sensor"],
        }
        targets = expand_brick_targets(model, scope)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].series_id, "s#b#vav#zat1")


class TestAssistantImport(unittest.TestCase):
    def test_extract_import_ready_json(self) -> None:
        raw = json.dumps(
            {
                "validation_notes": "ok",
                "import_ready_json": {
                    "sites": [{"id": "a"}],
                    "equipment": [],
                    "points": [],
                },
            }
        )
        out = extract_import_shape_from_llm_output(raw)
        self.assertIsNotNone(out)
        self.assertEqual(out["sites"][0]["id"], "a")


if __name__ == "__main__":
    unittest.main()
