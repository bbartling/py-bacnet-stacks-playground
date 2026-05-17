from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest


MODULE_PATH = Path("/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_target_scrape.py")


def load_module():
    spec = importlib.util.spec_from_file_location("point_target_scrape", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load point_target_scrape module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PointTargetScrapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_load_discovered_targets_filters_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "bacnet_discovery_latest.json"
            discovery_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {"instance": 3456790, "address": "192.168.204.14"},
                            {"instance": "3456789", "address": "192.168.204.13"},
                            {"instance": None, "address": "missing"},
                            {"instance": "bad", "address": "192.168.204.12"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            targets = self.module.load_discovered_targets(discovery_path)

        self.assertEqual(
            targets,
            [
                {"instance": 3456790, "address": "192.168.204.14"},
                {"instance": 3456789, "address": "192.168.204.13"},
            ],
        )

    def test_build_and_write_report_capture_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "bacnet_point_samples_latest.json"
            report = self.module.build_report(
                bind="192.168.204.18/24:47808",
                discovery_path="memory/integrations/bacnet_discovery_latest.json",
                targets=[{"instance": 3456790, "address": "192.168.204.14"}],
                target_results=[
                    {
                        "instance": 3456790,
                        "address": "192.168.204.14",
                        "ok": True,
                        "object_list": ["analog-input,1", "analog-value,2"],
                        "samples": [
                            {
                                "object": "analog-input,1",
                                "property": "present-value",
                                "ok": True,
                                "value": 72.5,
                            }
                        ],
                    }
                ],
                generated_at_utc="2026-05-16T21:00:00Z",
            )
            written_path = self.module.write_report(report, output_path)

            written = json.loads(written_path.read_text(encoding="utf-8"))

        self.assertEqual(str(written_path), str(output_path))
        self.assertEqual(written["target_count"], 1)
        self.assertEqual(written["ok_count"], 1)
        self.assertEqual(written["failed_count"], 0)
        self.assertEqual(written["sample_count"], 1)
        self.assertEqual(written["bind"], "192.168.204.18/24:47808")


if __name__ == "__main__":
    unittest.main()
