"""Tests for commissioning HTTP agent helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_PATH = ROOT / "edge_bacnet" / "commissioning_agent.py"


def _load_agent():
    spec = importlib.util.spec_from_file_location("commissioning_agent", AGENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["commissioning_agent"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDiscoverCommand(unittest.TestCase):
    def test_plain_ip_discover_cmd(self) -> None:
        mod = _load_agent()
        cmd = mod._discover_cmd(
            {
                "SITE_ID": "acme",
                "BUILDING_ID": "vm-bbartling",
                "BACNET_BIND": "10.200.200.185/24:47809",
                "BACNET_NAME": "GatewayVmBbartling",
                "BACNET_INSTANCE": "3456791",
                "DISCOVER_LOW": "8",
                "DISCOVER_HIGH": "8",
            },
            Path("/tmp/points_discovered.csv"),
        )
        self.assertIn("edge_bacnet.discover", " ".join(cmd))
        self.assertIn("--address", cmd)
        self.assertIn("10.200.200.185/24:47809", cmd)
        self.assertNotIn("--route-aware", cmd)

    def test_mstp_discover_cmd(self) -> None:
        mod = _load_agent()
        cmd = mod._discover_cmd(
            {
                "SITE_ID": "demo",
                "BUILDING_ID": "bens-office",
                "BACNET_BIND": "192.168.204.12/24:47809",
                "ROUTER_IP": "192.168.204.200",
                "MSTP_NET": "2000",
                "DISCOVER_LOW": "5007",
                "DISCOVER_HIGH": "5007",
            },
            Path("/tmp/out.csv"),
        )
        self.assertIn("--route-aware", cmd)
        self.assertIn("--router-ip", cmd)
        self.assertIn("192.168.204.200", cmd)


if __name__ == "__main__":
    unittest.main()
