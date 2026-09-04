#!/usr/bin/env python3
"""Offline tests for Pi-lab inventory allowlist / TX defaults (no LAN)."""
from __future__ import annotations

import pathlib
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


class InventorySafety(unittest.TestCase):
    def setUp(self) -> None:
        self.inv = yaml.safe_load((ROOT / "inventory.example.yml").read_text())
        self.group = self.inv["all"]["children"]["vibe13_pi_lab"]
        self.hosts = self.group["hosts"]
        self.vars = self.group["vars"]

    def test_allowlist_exact(self) -> None:
        allowed = self.vars["lab_allowed_hosts"]
        self.assertEqual(allowed["workerpi1"], "192.168.204.59")
        self.assertEqual(allowed["workerpi2"], "192.168.204.60")
        for name, host in self.hosts.items():
            self.assertEqual(host["ansible_host"], allowed[name])

    def test_tx_default_false(self) -> None:
        self.assertIs(self.vars["lab_allow_serial_tx"], False)

    def test_unique_macs_and_roles(self) -> None:
        macs = {h["lab_mstp_mac"] for h in self.hosts.values()}
        roles = {h["lab_role"] for h in self.hosts.values()}
        self.assertEqual(macs, {1, 2})
        self.assertEqual(roles, {"server", "probe"})

    def test_instances_not_tower(self) -> None:
        for h in self.hosts.values():
            self.assertNotEqual(h["lab_device_instance"], 123001)

    def test_by_id_seeded(self) -> None:
        self.assertIn("FTDI", self.hosts["workerpi1"]["lab_serial_by_id"])
        self.assertIn("1a86", self.hosts["workerpi2"]["lab_serial_by_id"])

    def test_no_localhost_host(self) -> None:
        for h in self.hosts.values():
            self.assertNotIn(h["ansible_host"], {"127.0.0.1", "localhost"})


class FixtureInventory(unittest.TestCase):
    def test_ci_fixture_has_doc_ips_only(self) -> None:
        path = ROOT / "files/fixtures/inventory.ci.yml"
        data = yaml.safe_load(path.read_text())
        hosts = data["all"]["children"]["vibe13_pi_lab"]["hosts"]
        for h in hosts.values():
            # RFC 5737 documentation range — never real Pi LAN in CI.
            self.assertTrue(h["ansible_host"].startswith("198.51.100."))


if __name__ == "__main__":
    try:
        import yaml as _  # noqa: F401
    except ImportError:
        print("PyYAML required", file=sys.stderr)
        sys.exit(2)
    unittest.main()
