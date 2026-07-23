"""G14 epoch history + model summary + envelope ratios."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.studio.g14_history import g14_epoch_figure, iter_g14_history
from wattlab.studio.idf_geometry import parse_idf_geometry
from wattlab.studio.model_summary import build_model_summary


def _wall_idf() -> str:
    return """  BuildingSurface:Detailed,
    WallA,                   !- Name
    Wall,                    !- Surface Type
    Const,                   !- Construction Name
    ZoneA,                   !- Zone Name
    ,                        !- Space Name
    Outdoors,                !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    SunExposed,              !- Sun Exposure
    WindExposed,             !- Wind Exposure
    0.5,                     !- View Factor to Ground
    4,                       !- Number of Vertices
    0.0,0.0,0.0,  !- X,Y,Z ==> Vertex 1 {m}
    10.0,0.0,0.0,  !- X,Y,Z ==> Vertex 2 {m}
    10.0,0.0,3.0,  !- X,Y,Z ==> Vertex 3 {m}
    0.0,0.0,3.0;  !- X,Y,Z ==> Vertex 4 {m}

  FenestrationSurface:Detailed,
    WinA,                    !- Name
    Window,                  !- Surface Type
    Glass,                   !- Construction Name
    WallA,                   !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    ,                        !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    2.0,0.0,0.5,  !- X,Y,Z ==> Vertex 1 {m}
    5.0,0.0,0.5,  !- X,Y,Z ==> Vertex 2 {m}
    5.0,0.0,2.0,  !- X,Y,Z ==> Vertex 3 {m}
    2.0,0.0,2.0;  !- X,Y,Z ==> Vertex 4 {m}

"""


def test_envelope_ratios_wwr():
    geom = parse_idf_geometry(_wall_idf())
    ratios = geom.envelope_ratios()
    assert ratios["wall_area_m2"] > 0
    assert ratios["window_area_m2"] > 0
    assert ratios["wwr"] is not None
    assert 0 < float(ratios["wwr"]) < 1
    assert ratios["wwr_pct"] == round(100.0 * float(ratios["wwr"]), 1)


def test_iter_g14_history_and_epoch(tmp_path: Path):
    runs = tmp_path / "runs"
    for i, nmbe in enumerate((20.0, 8.0, 3.0), start=1):
        d = runs / f"run_{i}"
        d.mkdir(parents=True)
        (d / "run_manifest.json").write_text(
            json.dumps(
                {
                    "run_id": f"run_{i}",
                    "status": "ok",
                    "started_at": f"2026-07-0{i}T12:00:00Z",
                    "finished_at": f"2026-07-0{i}T12:30:00Z",
                    "hypothesis": f"iter {i}",
                }
            ),
            encoding="utf-8",
        )
        (d / "calibration_scorecard.json").write_text(
            json.dumps(
                {
                    "utility_bills": {
                        "pass_fail": "PASS" if nmbe <= 5 else "FAIL",
                        "stats_electricity": {"nmbe_pct": nmbe, "cvrmse_pct": nmbe + 5},
                    }
                }
            ),
            encoding="utf-8",
        )
    rows = iter_g14_history(runs, limit=10)
    assert len(rows) == 3
    assert rows[0]["run_id"] == "run_1"
    assert rows[-1]["nmbe_elec_pct"] == 3.0
    fig = g14_epoch_figure(rows)
    assert len(fig.data) >= 2
    assert fig.layout.height >= 400
    legend_names = [getattr(t, "name", "") or "" for t in fig.data]
    assert any("G14 |NMBE| gate" in n for n in legend_names)
    assert any("G14 CV(RMSE) gate" in n for n in legend_names)


def test_build_model_summary(tmp_path: Path):
    run = tmp_path / "geo_dial"
    run.mkdir()
    (run / "model.idf").write_text(_wall_idf(), encoding="utf-8")
    (run / "dial_meta.json").write_text(
        json.dumps({"lights_w_per_m2": 4.5, "equip_w_per_m2": 4.2, "infil_mult": 1.4}),
        encoding="utf-8",
    )
    (run / "run_manifest.json").write_text(
        json.dumps({"run_id": "geo_dial", "status": "ok", "energyplus_version": "26.1"}),
        encoding="utf-8",
    )
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "floors": 6,
        "utility": {"elec_usd_per_kwh": 0.12},
    }
    summary = build_model_summary(answers, run)
    assert summary["project"]["city"] == "detroit"
    assert summary["geometry"]["floor_area_ft2"] == 140000
    assert summary["loads"]["lights_w_per_m2"] == 4.5
    assert summary["geometry"]["n_zones"] == 1
    assert summary["geometry"]["wwr_from_idf_pct"] is not None

    from wattlab.studio.model_summary import (
        build_assumption_rows,
        build_model_at_a_glance,
        filter_assumption_rows,
        missing_critical_inputs,
        rank_assumption_risk,
    )

    profile = {
        "field_sources": {
            "floor_area_ft2": {"value": 140000, "source": "user", "unit": "ft2"},
            "building_type": {"value": "office", "source": "default"},
        }
    }
    rows = build_assumption_rows(answers, run, profile=profile, summary=summary)
    assert any(r["parameter"] == "wwr_from_idf_pct" for r in rows)
    assert any(r["source"] == "INFERRED_FROM_GEOMETRY" for r in rows)
    assert any(r["parameter"] == "lights_w_per_m2" and r["value"] == 4.5 for r in rows)
    # WWR / area sanity: IDF WWR in (0, 100]
    wwr_row = next(r for r in rows if r["parameter"] == "wwr_from_idf_pct")
    assert wwr_row["value"] is not None and wwr_row["value"] != "—"
    assert 0 < float(wwr_row["value"]) <= 100

    glance = build_model_at_a_glance(summary, rows)
    assert glance["gross_floor_area_ft2"] == 140000
    assert glance["building_type"] == "office"
    assert "low_confidence_inputs" in glance

    risk = rank_assumption_risk(rows)
    assert risk
    assert any("risk_bucket" in r for r in risk)
    missing = missing_critical_inputs(rows)
    assert isinstance(missing, list)
    low = filter_assumption_rows(rows, mode="LOW CONFIDENCE")
    assert all(str(r["confidence"]).upper() in {"LOW", "UNKNOWN"} for r in low)

    # Documented profile source maps to USER_ENTERED
    area_rows = [r for r in rows if r["parameter"] == "floor_area_ft2" and r["category"] == "PROFILE"]
    assert area_rows and area_rows[0]["source"] == "USER_ENTERED"
