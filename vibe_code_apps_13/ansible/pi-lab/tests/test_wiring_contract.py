#!/usr/bin/env python3
"""Offline tests for wiring_contract (nonce, resistance, hosts, profile/duration)."""
from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_mod(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class WiringContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wc = load_mod("wiring_contract")
        cls.lab_ids = load_mod("lab_ids")

    def test_trusted_hosts_exported(self) -> None:
        self.assertEqual(self.lab_ids.TRUSTED_HOSTS["workerpi1"], "192.168.204.59")
        self.assertEqual(self.wc.TRUSTED_HOSTS["workerpi2"], "192.168.204.60")

    def test_check_host_rejects_bypass(self) -> None:
        with self.assertRaises(ValueError):
            self.wc.assert_trusted_host("workerpi1", "192.168.204.1")
        with self.assertRaises(ValueError):
            self.wc.assert_trusted_host("workerpi1", "198.51.100.59", allow_ci_doc=False)
        self.wc.assert_trusted_host("workerpi1", "198.51.100.59", allow_ci_doc=True)
        self.assertEqual(
            self.lab_ids.main(
                ["lab_ids.py", "check-host", "workerpi1", "192.168.204.59"]
            ),
            0,
        )
        self.assertEqual(
            self.lab_ids.main(
                ["lab_ids.py", "check-host", "workerpi1", "10.0.0.1"]
            ),
            1,
        )

    def test_resistance_rejects_nonnumeric(self) -> None:
        with self.assertRaises(ValueError):
            self.wc.validate_resistance_fields(
                {
                    "workerpi1_unpowered_ab_ohm": "OPERATOR_MEASURE",
                    "workerpi2_unpowered_ab_ohm": 120,
                    "combined_unpowered_ab_ohm": 60,
                },
                allow_override=False,
            )
        with self.assertRaises(ValueError):
            self.wc._require_number("x", "not-a-number")

    def test_profile_and_duration_bounds(self) -> None:
        self.assertEqual(self.wc.normalize_profile("raw-wire"), "raw-smoke")
        with self.assertRaises(ValueError):
            self.wc.normalize_profile("nope")
        self.assertEqual(self.wc.parse_duration_to_secs(None, "mstp-smoke"), 120)
        with self.assertRaises(ValueError):
            self.wc.parse_duration_to_secs("10", "mstp-soak")  # below 600
        self.assertEqual(self.wc.parse_duration_to_secs("1h", "mstp-soak"), 3600)

    def test_orientation_roles(self) -> None:
        self.assertEqual(
            self.wc.roles_for_orientation("workerpi1-server"),
            {"workerpi1": "server", "workerpi2": "probe"},
        )
        self.assertEqual(
            self.wc.roles_for_orientation("workerpi2-server"),
            {"workerpi1": "probe", "workerpi2": "server"},
        )

    def test_nonce_consume_once(self) -> None:
        hosts = {
            "workerpi1": {
                "ansible_host": "192.168.204.59",
                "adapter_model": "waveshare_c",
                "vid_pid": "0403:6001",
                "serial_by_id": "/dev/serial/by-id/A",
                "mac": 1,
                "device_instance": 123101,
            },
            "workerpi2": {
                "ansible_host": "192.168.204.60",
                "adapter_model": "waveshare_b",
                "vid_pid": "1a86:55d3",
                "serial_by_id": "/dev/serial/by-id/B",
                "mac": 2,
                "device_instance": 123102,
            },
        }
        inv = "fixture-inventory-bytes"
        man = self.wc.build_manifest(
            inventory_text=inv,
            project_sha="a" * 40,
            upstream_sha=self.wc.UPSTREAM_SHA,
            pair="cb",
            orientation="workerpi1-server",
            profile="mstp-smoke",
            baud=38400,
            max_master=2,
            max_info_frames=1,
            hosts=hosts,
            workerpi1_ohm=120.0,
            workerpi2_ohm=120.0,
            combined_ohm=60.0,
            bias_status="verified",
            polarity_confirmed=True,
            no_vcc_confirmed=True,
        )
        self.assertEqual(man["schema"], "vibe13_wiring_v2")
        self.assertFalse(man["nonce_consumed"])
        self.assertIn("expires_utc", man)
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "wiring.yml"
            import yaml

            path.write_text(yaml.safe_dump(man), encoding="utf-8")
            self.wc.consume_nonce(path)
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertTrue(data["nonce_consumed"])
            with self.assertRaises(ValueError):
                self.wc.consume_nonce(path)

    def test_pair_rejects_non_cb(self) -> None:
        with self.assertRaises(ValueError):
            self.wc.build_manifest(
                inventory_text="x",
                project_sha="a" * 40,
                upstream_sha=self.wc.UPSTREAM_SHA,
                pair="ab",
                orientation="workerpi1-server",
                profile="mstp-smoke",
                baud=38400,
                max_master=2,
                max_info_frames=1,
                hosts={},
                workerpi1_ohm=120,
                workerpi2_ohm=120,
                combined_ohm=60,
                bias_status="verified",
                polarity_confirmed=True,
                no_vcc_confirmed=True,
            )


if __name__ == "__main__":
    unittest.main()
