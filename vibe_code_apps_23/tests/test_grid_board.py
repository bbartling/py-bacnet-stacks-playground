"""Unit tests for Studio grid-search progress + ranking fixtures."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from vibe23.studio.search_progress import (
    candidate_rows_for_animation,
    dimensions_from_form,
    enumerate_from_form,
    form_matches_fixture_catalog,
    format_dimension_values,
    load_grid_ranking,
    parse_dimension_values,
    qtable_matrix,
    search_progress_state,
    season_dimension_defaults,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio"


@pytest.mark.parametrize("season", ["summer", "winter"])
def test_load_grid_ranking_shape(season: str) -> None:
    payload = load_grid_ranking(season)
    assert payload["schema"] == "vibe23.residential_grid_ranking.v1"
    rows = payload["rows"]
    assert isinstance(rows, list) and rows
    for row in rows:
        for key in (
            "candidate_id",
            "billing_cost",
            "peak_kw",
            "total_kwh",
            "comfort_ok",
            "soft_ok",
            "wall_seconds",
            "action_json",
            "idf_sha256",
        ):
            assert key in row
    anim = candidate_rows_for_animation(payload)
    assert all(r["candidate_id"] != "BASELINE" for r in anim)
    assert len(anim) == 169
    assert payload.get("fixture_kind") == "ILLUSTRATIVE_PHYSICS_PROXY" or "winner" in payload


def test_parse_dimension_values() -> None:
    assert parse_dimension_values("13.0, 14.0") == (13.0, 14.0)
    with pytest.raises(ValueError):
        parse_dimension_values("")
    with pytest.raises(ValueError):
        parse_dimension_values("1, 1")


def test_enumerate_from_form_stable_ids() -> None:
    from vibe23.residential.experiment import default_thermostat_candidates

    dims = season_dimension_defaults("summer")
    form = {d.name: format_dimension_values(d.values) for d in dims}
    cands = enumerate_from_form(form, season="summer")
    assert len(cands) == 169
    assert len(default_thermostat_candidates(season="winter")) == 169
    assert cands[0].candidate_id.startswith("GRID_0000_")
    assert form_matches_fixture_catalog(form, season="summer")
    form2 = dict(form)
    form2["pre_center_f"] = "70.0"
    cands2 = enumerate_from_form(form2, season="summer")
    assert len(cands2) == 13
    assert not form_matches_fixture_catalog(form2, season="summer")


def test_malformed_dimension_raises() -> None:
    dims = season_dimension_defaults("summer")
    form = {d.name: format_dimension_values(d.values) for d in dims}
    form["event_start"] = "not-a-number"
    with pytest.raises(ValueError):
        dimensions_from_form(form, season="summer")


def test_search_progress_state_math() -> None:
    ranking = load_grid_ranking("summer")
    rows = candidate_rows_for_animation(ranking)
    n = len(rows)
    z = search_progress_state(rows, 0)
    assert z["fraction"] == 0.0
    assert z["eplus_runs"] == 1
    assert z["total_runs"] == n + 1
    assert z["feasible"] == 0
    assert z["rejected"] == 0
    assert z["best_row"] is None
    assert z["log_lines"] == []

    full = search_progress_state(rows, n)
    assert full["fraction"] == pytest.approx(1.0)
    assert full["eplus_runs"] == n + 1
    assert full["feasible"] + full["rejected"] == n
    assert full["wall_seconds_so_far"] >= 0.0

    prev_wall = -1.0
    prev_best = float("inf")
    for k in range(0, n + 1):
        st = search_progress_state(rows, k)
        assert st["wall_seconds_so_far"] >= prev_wall - 1e-9
        prev_wall = st["wall_seconds_so_far"]
        assert st["feasible"] + st["rejected"] == k
        if st["best_cost"] is not None:
            assert st["best_cost"] <= prev_best + 1e-9
            prev_best = st["best_cost"]
            assert math.isfinite(st["best_cost"])


def test_ranking_fixture_files_exist() -> None:
    assert (FIXTURES / "summer_thermostat_grid_ranking.json").is_file()
    assert (FIXTURES / "winter_thermostat_grid_ranking.json").is_file()
    assert (FIXTURES / "summer_twin_export.json").is_file()
    assert (FIXTURES / "winter_twin_export.json").is_file()


def test_qtable_matrix_shape_from_fixture() -> None:
    payload = load_grid_ranking("summer")
    rows = payload["rows"]
    matrix = qtable_matrix(rows)
    assert len(matrix["pre_centers"]) == 13
    assert len(matrix["event_centers"]) == 13
    assert len(matrix["costs"]) == 13
    assert all(len(row) == 13 for row in matrix["costs"])
    assert matrix["n_filled"] == 169

    partial = qtable_matrix(rows, evaluated=0)
    assert partial["n_filled"] == 0
