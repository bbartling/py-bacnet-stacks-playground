"""IDF geometry viewer + publish model.idf coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIVE_ZONE = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"

# Tiny synthetic shoebox — different footprint than 5Zone (proves non-hardcoded)
_SYNTH_IDF = """
  BuildingSurface:Detailed,
    Wall-South,              !- Name
    WALL,                    !- Surface Type
    ExtWall,                 !- Construction Name
    ZoneA,                   !- Zone Name
    ,                        !- Space Name
    Outdoors,                !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    SunExposed,              !- Sun Exposure
    WindExposed,             !- Wind Exposure
    0.5,                     !- View Factor to Ground
    4,                       !- Number of Vertices
    0,0,0,  !- X,Y,Z ==> Vertex 1 {m}
    60,0,0,  !- X,Y,Z ==> Vertex 2 {m}
    60,0,20,  !- X,Y,Z ==> Vertex 3 {m}
    0,0,20;  !- X,Y,Z ==> Vertex 4 {m}

  BuildingSurface:Detailed,
    Roof-1,                  !- Name
    ROOF,                    !- Surface Type
    RoofConst,               !- Construction Name
    ZoneA,                   !- Zone Name
    ,                        !- Space Name
    Outdoors,                !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    SunExposed,              !- Sun Exposure
    WindExposed,             !- Wind Exposure
    0.0,                     !- View Factor to Ground
    4,                       !- Number of Vertices
    0,0,20,
    0,40,20,
    60,40,20,
    60,0,20;
"""


def test_parse_5zone_idf_surfaces():
    from wattlab.studio.idf_geometry import idf_massing_figure, parse_idf_geometry

    assert FIVE_ZONE.is_file()
    geom = parse_idf_geometry(FIVE_ZONE)
    assert len(geom.surfaces) >= 10
    assert any(z.startswith("SPACE") for z in geom.zone_names)
    summary = geom.summary()
    assert summary["bbox_m"]["dx"] > 1
    fig = idf_massing_figure(geom)
    assert len(fig.data) >= 1


def test_synthetic_idf_different_bbox_from_5zone():
    from wattlab.studio.idf_geometry import parse_idf_geometry

    synth = parse_idf_geometry(_SYNTH_IDF)
    five = parse_idf_geometry(FIVE_ZONE)
    assert synth.summary()["bbox_m"]["dx"] == pytest.approx(60.0)
    assert five.summary()["bbox_m"]["dx"] == pytest.approx(30.5)
    assert synth.summary()["bbox_m"]["dx"] != five.summary()["bbox_m"]["dx"]


def test_publish_copies_model_idf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from wattlab.studio.ep_viz import find_run_idf, publish_run_for_studio

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    src = tmp_path / "artifacts" / "run_src"
    src.mkdir(parents=True)
    (src / "baseline.idf").write_text(_SYNTH_IDF, encoding="utf-8")
    (src / "eplusout.csv").write_text("Date/Time\n", encoding="utf-8")
    dest = publish_run_for_studio(src, run_id="geo_test", dest_root=tmp_path / "runs" / "geo_test")
    assert (dest / "model.idf").is_file()
    assert find_run_idf(dest) == dest / "model.idf"
    from wattlab.studio.idf_geometry import parse_idf_geometry

    assert parse_idf_geometry(dest / "model.idf").surfaces


def test_studio_apptest_twin_no_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    import json

    from streamlit.testing.v1 import AppTest

    from wattlab.studio.bootstrap import build_bootstrap_payload, write_bootstrap
    from wattlab.studio.ep_viz import publish_run_for_studio

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    (tmp_path / "reports").mkdir(parents=True)
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "floors": 6,
        "lat": 42.33,
        "lon": -83.04,
    }
    (tmp_path / "reports" / "answers.json").write_text(json.dumps(answers), encoding="utf-8")

    src = tmp_path / "art"
    src.mkdir()
    if FIVE_ZONE.is_file():
        (src / "baseline.idf").write_bytes(FIVE_ZONE.read_bytes())
    else:
        (src / "baseline.idf").write_text(_SYNTH_IDF, encoding="utf-8")
    fixture_csv = ROOT / "tests" / "fixtures" / "eplusout" / "eplusout.csv"
    if fixture_csv.is_file():
        (src / "eplusout.csv").write_bytes(fixture_csv.read_bytes())
    else:
        (src / "eplusout.csv").write_text("Date/Time\n", encoding="utf-8")
    publish_run_for_studio(src, run_id="apptest_geo", dest_root=tmp_path / "runs" / "apptest_geo")

    write_bootstrap(
        build_bootstrap_payload(
            preferred_run_id="apptest_geo",
            answers_path="reports/answers.json",
        )
    )
    at = AppTest.from_file(str(ROOT / "studio.py"), default_timeout=60)
    at.run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Twin / calibrate").run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
