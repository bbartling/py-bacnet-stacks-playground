"""Catalog expectations tied to the pinned OpenFDD hash — not a universal 59."""

from __future__ import annotations

import json
from pathlib import Path

PIN_PATH = Path(__file__).resolve().parent / "golden" / "expected_catalog.json"


def load_catalog_pin() -> dict:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def pinned_diagnostic_count() -> int:
    return int(load_catalog_pin()["diagnostic_count"])


def assert_live_catalog_matches_pin() -> dict:
    from open_fdd.catalog import rule_catalog_hash
    from open_fdd import __version__

    pin = load_catalog_pin()
    live = rule_catalog_hash()
    allowed = {
        pin["rule_catalog_hash"],
        pin.get("pypi_430_wheel_hash"),
        pin.get("openfdd_710_sched1_hash"),
    } - {None, ""}
    assert live in allowed, (
        f"Installed open-fdd catalog hash {live} not in {sorted(allowed)}. "
        "Update tests/golden/expected_catalog.json only after reviewing the new catalog."
    )
    assert str(__version__).split("+", 1)[0] == pin["open_fdd_version"]
    return pin
