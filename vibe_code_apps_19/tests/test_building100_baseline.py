"""Building 100 cartesian baseline — optional real package, catalog-hash tied."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.catalog_contract import assert_live_catalog_matches_pin


def _building100_zip() -> Path | None:
    env = (os.environ.get("VIBE19_BUILDING100_ZIP") or os.environ.get("VIBE19_TEST_PACKAGE_DIR") or "").strip()
    candidates: list[Path] = []
    if env:
        p = Path(env)
        candidates.append(p if p.is_file() else p / "BUILDING_100.zip")
        candidates.append(p / "BUILDING_100_openfdd.zip")
    candidates.extend(
        [
            Path("/home/ben/raw_BUILDING_100_openfdd.zip"),
            Path("/home/ben/BUILDING_100_openfdd.zip"),
        ]
    )
    for c in candidates:
        if c.is_file():
            return c
    return None


@pytest.mark.optional_zip
def test_building100_equipment_and_cartesian():
    pin = assert_live_catalog_matches_pin()
    zpath = _building100_zip()
    if zpath is None:
        pytest.skip("Building 100 zip not available")
    from app.package_io import load_package_zip, wipe_workdir

    result = load_package_zip(zpath.read_bytes())
    try:
        assert len(result.frames) == pin["building100_equipment"]
        health = (result.report or {}).get("package_health") or {}
        topo = health.get("topology") or {}
        # parent_ahu must not invent AHU → tower mappings
        stale = topo.get("stale_samples") or []
        assert "100" not in stale
        assert not any(str(s).isdigit() for s in stale)
    finally:
        wipe_workdir(result.workdir)


@pytest.mark.optional_zip
def test_building100_result_row_count():
    pin = assert_live_catalog_matches_pin()
    zpath = _building100_zip()
    if zpath is None:
        pytest.skip("Building 100 zip not available")
    from app.agent_api import export_agent_bundle, load_package_path, run_rules
    from app.package_io import wipe_workdir

    ds = load_package_path(zpath)
    try:
        run = run_rules(ds)
        expected = pin["building100_equipment"] * pin["diagnostic_count"]
        assert expected == pin["building100_result_rows"]
        assert run.meta["result_count"] == expected
    finally:
        if ds.workdir:
            wipe_workdir(ds.workdir)
