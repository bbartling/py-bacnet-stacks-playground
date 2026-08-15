"""Refuse stale OpenFDD wheels and pin the catalog hash."""

from __future__ import annotations

import pytest

from app.openfdd_runtime import OpenFddVersionError, require_supported_open_fdd
from tests.catalog_contract import assert_live_catalog_matches_pin, pinned_diagnostic_count


def test_require_supported_open_fdd():
    ver = require_supported_open_fdd()
    assert ver.startswith("4.4.")


def test_catalog_pin_matches_installed_package():
    pin = assert_live_catalog_matches_pin()
    from app.rules import CANONICAL_RULE_COUNT

    assert CANONICAL_RULE_COUNT == pin["diagnostic_count"] == pinned_diagnostic_count()


def test_refuse_old_version(monkeypatch):
    from app import openfdd_runtime as rt

    monkeypatch.setattr(rt, "installed_open_fdd_version", lambda: "4.2.0")
    with pytest.raises(OpenFddVersionError, match="too old"):
        rt.require_supported_open_fdd()


def test_refuse_host_301(monkeypatch):
    from app import openfdd_runtime as rt

    monkeypatch.setattr(rt, "installed_open_fdd_version", lambda: "3.0.1")
    with pytest.raises(OpenFddVersionError, match="too old"):
        rt.require_supported_open_fdd()


def test_refuse_host_430(monkeypatch):
    from app import openfdd_runtime as rt

    monkeypatch.setattr(rt, "installed_open_fdd_version", lambda: "4.3.0")
    with pytest.raises(OpenFddVersionError, match="4.3.0"):
        rt.require_supported_open_fdd()
