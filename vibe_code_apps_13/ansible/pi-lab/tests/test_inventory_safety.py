#!/usr/bin/env python3
"""Offline tests for Pi-lab inventory allowlist / TX defaults / id safety (no LAN)."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_lab_ids():
    spec = importlib.util.spec_from_file_location("lab_ids", SCRIPTS / "lab_ids.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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

    def test_official_bc_chipset_map(self) -> None:
        # C = FTDI; B = CH343 (corrected vs early PR #135 letter swap).
        self.assertEqual(self.hosts["workerpi1"]["lab_adapter_model"], "waveshare_c")
        self.assertEqual(self.hosts["workerpi1"]["lab_adapter_vid_pid"], "0403:6001")
        self.assertEqual(self.hosts["workerpi2"]["lab_adapter_model"], "waveshare_b")
        self.assertEqual(self.hosts["workerpi2"]["lab_adapter_vid_pid"], "1a86:55d3")

    def test_no_localhost_host(self) -> None:
        for h in self.hosts.values():
            self.assertNotIn(h["ansible_host"], {"127.0.0.1", "localhost"})

    def test_exactly_two_hosts(self) -> None:
        self.assertEqual(len(self.hosts), 2)


class FixtureInventory(unittest.TestCase):
    def test_ci_fixture_has_doc_ips_only(self) -> None:
        path = ROOT / "files/fixtures/inventory.ci.yml"
        data = yaml.safe_load(path.read_text())
        hosts = data["all"]["children"]["vibe13_pi_lab"]["hosts"]
        for h in hosts.values():
            self.assertTrue(h["ansible_host"].startswith("198.51.100."))
        self.assertEqual(hosts["workerpi1"]["lab_adapter_model"], "waveshare_c")
        self.assertEqual(hosts["workerpi2"]["lab_adapter_model"], "waveshare_b")


class RunIdValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.lab_ids = load_lab_ids()

    def test_accepts_timestamp(self) -> None:
        self.assertEqual(self.lab_ids.validate_run_id("20260905T120000Z"), "20260905T120000Z")

    def test_rejects_traversal(self) -> None:
        for bad in ("../etc", "a/b", "a\\b", "..", ".", ""):
            with self.assertRaises(ValueError):
                self.lab_ids.validate_run_id(bad)

    def test_git_sha(self) -> None:
        sha = "a" * 40
        self.assertEqual(self.lab_ids.validate_git_sha(sha), sha)
        with self.assertRaises(ValueError):
            self.lab_ids.validate_git_sha("deadbeef")


class WiringRunGateDocs(unittest.TestCase):
    def test_run_requires_allow_tx(self) -> None:
        text = (ROOT / "playbooks/run.yml").read_text()
        self.assertIn("lab_allow_tx", text)
        self.assertIn("Mere wiring.local.yml", text)

    def test_confirm_writes_schema(self) -> None:
        text = (ROOT / "playbooks/confirm_wiring.yml").read_text()
        self.assertIn("vibe13_wiring_v1", text)
        self.assertIn("inventory_digest_sha256", text)

    def test_build_refuses_x86_fallback(self) -> None:
        text = (ROOT / "scripts/build_release.sh").read_text()
        self.assertIn("Refusing to package x86_64", text)
        self.assertNotIn("Building x86_64 host bins for packaging smoke", text)


if __name__ == "__main__":
    try:
        import yaml as _  # noqa: F401
    except ImportError:
        print("PyYAML required", file=sys.stderr)
        sys.exit(2)
    unittest.main()
