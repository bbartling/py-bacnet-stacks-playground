"""Edge CSV config loader."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from edge_bacnet.config import CSV_FIELDNAMES, group_by_device, load_enabled_points  # noqa: E402


class TestCsvConfigLoader(unittest.TestCase):
    def test_load_enabled_only(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            w.writeheader()
            w.writerow(
                {
                    "device_instance": "3456788",
                    "device_address": "192.168.1.10",
                    "object_type": "analog-input",
                    "object_instance": "1",
                    "object_name": "SAT",
                    "description": "",
                    "present_value": "",
                    "units": "degF",
                    "site_id": "acme",
                    "building_id": "tower-a",
                    "system_id": "ahu-1",
                    "brick_class": "Supply_Air_Temperature_Sensor",
                    "brick_tag": "SAT",
                    "enabled": "1",
                    "poll_interval_s": "",
                    "point_id": "",
                    "series_id": "",
                }
            )
            w.writerow(
                {
                    "device_instance": "3456788",
                    "device_address": "192.168.1.10",
                    "object_type": "analog-input",
                    "object_instance": "2",
                    "object_name": "disabled",
                    "description": "",
                    "present_value": "",
                    "units": "",
                    "site_id": "acme",
                    "building_id": "tower-a",
                    "system_id": "ahu-1",
                    "brick_class": "",
                    "brick_tag": "",
                    "enabled": "0",
                    "poll_interval_s": "",
                    "point_id": "",
                    "series_id": "",
                }
            )
            path = f.name

        pts = load_enabled_points(path)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].brick_tag, "SAT")
        grouped = group_by_device(pts)
        self.assertEqual(len(grouped), 1)


if __name__ == "__main__":
    unittest.main()
