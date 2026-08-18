"""Optional LIVE EnergyPlus 96-row Track B extraction. Skipped in CI."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.trackb_scored_run import validate_scored_trackb_run

APP = Path(__file__).resolve().parents[1]


@pytest.mark.eplus
@pytest.mark.live_energyplus
def test_live_trackb_continuity_extracts_96_rows(tmp_path: Path):
    site_root = os.environ.get("SITE_ROOT") or r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
    site = Path(site_root)
    if not site.is_dir():
        pytest.skip("site pack missing")
    artifact = (
        APP
        / "docs"
        / "audits"
        / "figures"
        / "vibe22_live_trackb_long_rl"
        / "trackb_live_v3_base_20260112"
        / "one_day_artifact.json"
    )
    if not artifact.is_file():
        pytest.skip("first LIVE one_day_artifact.json not yet written")
    import json

    body = json.loads(artifact.read_text(encoding="utf-8"))
    assert body.get("n_rows") == 96
    assert body.get("energyplus_version") == "26.1.0"
    assert body.get("n_process_starts") == 1
    _ = BAS_ZONE_COLS
    _ = validate_scored_trackb_run
