"""Unit tests for APIHelper-08-style Twin viz helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from wattlab.energyplus.timeseries import parse_eplusout_timeseries
from wattlab.studio.ep_viz import (
    floor_plan_figure,
    install_demo_replay,
    map_zones_to_roles,
    outdoor_figure,
    publish_run_for_studio,
    read_run_progress,
    zone_mean_by_role,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eplusout" / "eplusout.csv"


def test_map_prototype_zones_to_compass_roles():
    roles = map_zones_to_roles(["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"])
    assert roles["SPACE1-1"] == "south"
    assert roles["SPACE5-1"] == "center"


def test_floor_plan_and_oa_from_fixture():
    ts = parse_eplusout_timeseries(FIXTURE)
    roles = zone_mean_by_role(ts)
    assert roles
    fig = floor_plan_figure(roles)
    assert fig is not None
    oa = outdoor_figure(ts.outdoor)
    assert oa is not None


def test_demo_replay_install(tmp_path: Path):
    dest = tmp_path / "demo_replay"
    install_demo_replay(dest, FIXTURE)
    info = read_run_progress(dest)
    assert info["replay"] is True
    assert info["progress"] == 100
    assert (dest / "eplusout.csv").is_file()
    assert (dest.parent / "CURRENT_RUN.txt").is_file()


def test_publish_run_for_studio_writes_current_pointer(tmp_path: Path):
    src = tmp_path / "wattlab_sim"
    (src / "sim_baseline").mkdir(parents=True)
    shutil.copy2(FIXTURE, src / "sim_baseline" / "eplusout.csv")
    (src / "run_manifest.json").write_text(
        '{"run_id":"t1","status":"SUCCESS"}', encoding="utf-8"
    )
    dest = tmp_path / "runs" / "t1"
    published = publish_run_for_studio(src, run_id="t1", dest_root=dest)
    assert (published / "eplusout.csv").is_file()
    pointer = published.parent / "CURRENT_RUN.txt"
    assert pointer.is_file()
    assert pointer.read_text(encoding="utf-8").strip() == str(published.resolve())
