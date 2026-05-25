"""Route segment parsing for telemetry / commissioning APIs."""

from __future__ import annotations

import unittest


def _site_building(path: str, prefix: str) -> tuple[str, str]:
    parts = [p for p in path.split("/") if p]
    # api/telemetry/flow/{site}/{building}
    assert path.startswith(prefix)
    return parts[3], parts[4]


class TestTelemetryRoutes(unittest.TestCase):
    def test_flow_path_segments(self):
        site, bld = _site_building(
            "/api/telemetry/flow/demo/bens-office", "/api/telemetry/flow/"
        )
        self.assertEqual(site, "demo")
        self.assertEqual(bld, "bens-office")

    def test_commissioning_path_segments(self):
        site, bld = _site_building(
            "/api/commissioning/status/demo/bens-office",
            "/api/commissioning/status/",
        )
        self.assertEqual(site, "demo")
        self.assertEqual(bld, "bens-office")


if __name__ == "__main__":
    unittest.main()
