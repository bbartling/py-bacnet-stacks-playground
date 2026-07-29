"""G14 epoch history + model summary + envelope ratios."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.studio.g14_history import (
    assign_run_numbers,
    building_family_from_run_id,
    g14_epoch_figure,
    iter_g14_history,
    pick_best_g14_run,
    run_id_short_stem,
)
from wattlab.studio.idf_geometry import parse_idf_geometry
from wattlab.studio.model_summary import build_dial_knobs_rows, build_model_summary


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
    numbered = assign_run_numbers(rows)
    assert [r["run"] for r in numbered] == [1, 2, 3]
    best = pick_best_g14_run(numbered)
    assert best is not None
    assert best["run_id"] == "run_3"  # PASS + lowest error
    # Prefer PASS over lower FAIL error
    fail_better = [
        {**numbered[0], "pass_fail": "FAIL", "nmbe_elec_pct": 1.0, "cvrmse_elec_pct": 2.0},
        {**numbered[2], "pass_fail": "PASS", "nmbe_elec_pct": 4.0, "cvrmse_elec_pct": 10.0},
    ]
    assert pick_best_g14_run(fail_better)["run_id"] == "run_3"
    fig = g14_epoch_figure(rows)
    assert len(fig.data) >= 2
    assert fig.layout.height >= 400
    legend_names = [getattr(t, "name", "") or "" for t in fig.data]
    assert any("G14 |NMBE| gate" in n for n in legend_names)
    assert any("G14 CV(RMSE) gate" in n for n in legend_names)


def _write_g14_run(
    runs: Path,
    run_id: str,
    *,
    day: int,
    nmbe: float,
    cvrmse: float,
    pass_fail: str,
) -> None:
    d = runs / run_id
    d.mkdir(parents=True)
    (d / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "started_at": f"2026-07-{day:02d}T12:00:00Z",
                "finished_at": f"2026-07-{day:02d}T12:30:00Z",
                "hypothesis": run_id,
            }
        ),
        encoding="utf-8",
    )
    (d / "calibration_scorecard.json").write_text(
        json.dumps(
            {
                "utility_bills": {
                    "pass_fail": pass_fail,
                    "stats_electricity": {"nmbe_pct": nmbe, "cvrmse_pct": cvrmse},
                }
            }
        ),
        encoding="utf-8",
    )


def test_building_family_helpers():
    assert building_family_from_run_id("geo_b100_6stack_shape_r56_sched_mild") == "geo_b100"
    assert building_family_from_run_id("geo_b50_i32_freecool_julHW") == "geo_b50"
    assert run_id_short_stem("geo_b100_6stack_shape_r56_sched_mild") == "r56"
    assert run_id_short_stem("geo_b50_i32_freecool_julHW") == "i32"


def test_g14_chart_scopes_to_building_family(tmp_path: Path):
    """B100 filter must never plot B50 points; best PASS is r56-like, not B50 i32."""
    runs = tmp_path / "runs"
    # Newer B50 FAIL (would look like “late iter” in mixed mtime soup)
    _write_g14_run(
        runs,
        "geo_b50_i32_freecool_julHW",
        day=20,
        nmbe=2.0,
        cvrmse=19.5,
        pass_fail="FAIL",
    )
    _write_g14_run(
        runs,
        "geo_b50_i31_earlier",
        day=18,
        nmbe=4.0,
        cvrmse=18.0,
        pass_fail="FAIL",
    )
    # Older B100 PASS (true best for B100)
    _write_g14_run(
        runs,
        "geo_b100_6stack_shape_r56_sched_mild",
        day=10,
        nmbe=1.5,
        cvrmse=8.0,
        pass_fail="PASS",
    )
    _write_g14_run(
        runs,
        "geo_b100_6stack_shape_r55_prior",
        day=8,
        nmbe=6.0,
        cvrmse=16.0,
        pass_fail="FAIL",
    )

    b100 = assign_run_numbers(
        iter_g14_history(runs, limit=80, building_family="geo_b100")
    )
    ids = [r["run_id"] for r in b100]
    assert ids == [
        "geo_b100_6stack_shape_r55_prior",
        "geo_b100_6stack_shape_r56_sched_mild",
    ]
    assert all(str(r["run_id"]).startswith("geo_b100") for r in b100)
    assert "geo_b50_i32_freecool_julHW" not in ids
    best = pick_best_g14_run(b100)
    assert best is not None
    assert best["run_id"] == "geo_b100_6stack_shape_r56_sched_mild"
    assert best["pass_fail"] == "PASS"

    fig = g14_epoch_figure(b100, building_family="geo_b100")
    customdatas = []
    for t in fig.data:
        cd = getattr(t, "customdata", None)
        if cd is not None:
            customdatas.extend([str(x) for x in cd if x])
    hover_blob = " ".join(
        str(getattr(t, "text", "") or "")
        + " "
        + " ".join(str(x) for x in (getattr(t, "customdata", None) or []))
        for t in fig.data
    )
    assert "geo_b100_6stack_shape_r56_sched_mild" in hover_blob
    assert "geo_b50_i32" not in hover_blob
    assert "geo_b50" not in hover_blob
    legend_names = [getattr(t, "name", "") or "" for t in fig.data]
    assert any(n == "G14 PASS" for n in legend_names)

    # Mixed / unfiltered still returns both families (explicit All path)
    mixed = iter_g14_history(runs, limit=80)
    mixed_ids = {r["run_id"] for r in mixed}
    assert "geo_b50_i32_freecool_julHW" in mixed_ids
    assert "geo_b100_6stack_shape_r56_sched_mild" in mixed_ids


def test_build_dial_knobs_rows(tmp_path: Path):
    run = tmp_path / "knobs"
    run.mkdir()
    (run / "dial_meta.json").write_text(
        json.dumps(
            {
                "lights_w_per_m2": 5.0,
                "equip_w_per_m2": 6.0,
                "infil_mult": 1.2,
                "shgc": 0.35,
                "wwr": 0.4,
                "hypothesis": "raise LPD",
            }
        ),
        encoding="utf-8",
    )
    (run / "run_manifest.json").write_text(
        json.dumps({"run_id": "knobs", "status": "ok"}),
        encoding="utf-8",
    )
    rows = build_dial_knobs_rows({"building_type": "office"}, run)
    by_knob = {r["knob"]: r["value"] for r in rows}
    assert by_knob["lights_w_per_m2"] == 5.0
    assert by_knob["hypothesis"] == "raise LPD"
    assert by_knob["infil_mult"] == 1.2


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
