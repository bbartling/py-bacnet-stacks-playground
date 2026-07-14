"""Analytics golden baseline — lock Overview/RCx/metering/rule digests for perf iteration."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from app.agent_api import load_package_path
from app.analytics_baseline import (
    GOLDEN_TABLE_NAMES,
    UPDATE_ENV,
    assert_matches_golden,
    compute_analytics_bundle,
    fingerprints_for_bundle,
    golden_dir_default,
    maybe_assert_timings,
)
from tests.fixtures.analytics_pkg_builder import FIXTURE_ROOT, write_analytics_pkg

ROOT = Path(__file__).resolve().parents[1]


def _optional_building100_dir() -> Path | None:
    env = (os.environ.get("VIBE19_TEST_PACKAGE_DIR") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir() and (p / "BUILDING_100.zip").is_file():
            return p
    candidates = [
        Path(
            r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
            r"\workspace\imports\hvac_systems_CLEANED"
        ),
        ROOT / "data" / "hvac_systems_CLEANED",
    ]
    for c in candidates:
        if c.is_dir() and (c / "BUILDING_100.zip").is_file():
            return c
    return None


@pytest.fixture(scope="module")
def analytics_fixture_pkg() -> Path:
    """Ensure on-disk fixture exists (idempotent rewrite keeps deterministic content)."""
    return write_analytics_pkg(FIXTURE_ROOT)


def test_analytics_golden_baseline(analytics_fixture_pkg: Path, capsys):
    t_load0 = time.perf_counter()
    ds = load_package_path(analytics_fixture_pkg)
    load_s = time.perf_counter() - t_load0
    assert ds.building_id == "ANALYTICS_GOLDEN_B1"
    assert len(ds.frames) >= 5
    assert ds.has_web_weather

    bundle = compute_analytics_bundle(ds)
    for name in GOLDEN_TABLE_NAMES:
        assert name in bundle.tables

    assert_matches_golden(bundle)

    report = maybe_assert_timings(bundle.timings_s, load_s=load_s)
    # Soft timing report (visible with -s)
    print(
        "analytics_golden timings_s:",
        json.dumps({k: round(v, 4) for k, v in report.items()}, sort_keys=True),
    )
    # Ensure report keys exist
    assert "analytics_s" in report and "rcx_s" in report and "rules_s" in report
    assert "total_s" in report


def test_analytics_golden_fingerprints_file_present():
    fp = golden_dir_default() / "fingerprints.json"
    if os.environ.get(UPDATE_ENV, "").strip() in {"1", "true", "True", "yes", "YES"}:
        pytest.skip("updating goldens — fingerprints rewritten by assert test")
    assert fp.is_file(), f"Missing {fp}; run with {UPDATE_ENV}=1 once to seed goldens"


def test_building100_analytics_digest_optional():
    """Optional heavy lane: fingerprint digests only (no huge CSV commit)."""
    pkg_dir = _optional_building100_dir()
    if pkg_dir is None:
        pytest.skip("optional BUILDING_100.zip not available")

    digest_path = golden_dir_default() / "building100_fingerprints.json"
    update = os.environ.get(UPDATE_ENV, "").strip() in {"1", "true", "True", "yes", "YES"}
    if not update and not digest_path.is_file():
        pytest.skip(
            f"No committed {digest_path.name}; set {UPDATE_ENV}=1 with BUILDING_100 available to seed"
        )

    zpath = pkg_dir / "BUILDING_100.zip"
    t_load0 = time.perf_counter()
    ds = load_package_path(zpath)
    load_s = time.perf_counter() - t_load0

    bundle = compute_analytics_bundle(ds, run_rules_digest=True)
    fps = fingerprints_for_bundle(bundle)
    report = maybe_assert_timings(bundle.timings_s, load_s=load_s)

    if update:
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        digest_path.write_text(json.dumps(fps, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("Wrote", digest_path)
        print("building100 timings_s:", json.dumps({k: round(v, 4) for k, v in report.items()}))
        return

    want = json.loads(digest_path.read_text(encoding="utf-8"))
    timing_preview = {k: round(v, 4) for k, v in report.items()}
    assert fps == want, (
        "BUILDING_100 analytics fingerprint mismatch — "
        f"set {UPDATE_ENV}=1 only after intentional analytics changes. "
        f"timings={timing_preview}"
    )
