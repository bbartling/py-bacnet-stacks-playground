import json

import pytest

from vibe23.cli import _enumerate_grid, _parse_replacements, _score, build_parser


def test_parser_exposes_pipeline_commands():
    help_text = build_parser().format_help()
    for command in (
        "download",
        "export-openfdd",
        "validate-model-ledger",
        "render-model-seed",
        "inspect-rllib",
        "inspect-tariff",
        "enumerate-grid",
        "energyplus-doctor",
        "run-eplus-smoke",
        "inspect-eplus-run",
        "plot-calibration",
        "plot-calibration-campaign",
    ):
        assert command in help_text


def test_replacement_parser_rejects_duplicates():
    assert _parse_replacements(["VERSION=24.2", "NAME=B59"]) == {"VERSION": "24.2", "NAME": "B59"}
    with pytest.raises(ValueError, match="more than once"):
        _parse_replacements(["NAME=A", "NAME=B"])


def test_grid_cli_writes_enumeration_only_manifest(tmp_path):
    source = tmp_path / "grid.json"
    output = tmp_path / "candidates.json"
    source.write_text(
        json.dumps(
            {
                "schema": "vibe23.grid_declaration.v1",
                "dimensions": [
                    {"name": "occupied_cooling_f", "values": [72, 74]},
                    {"name": "recovery_minutes", "values": [0, 30]},
                ],
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(["enumerate-grid", "--grid", str(source), "--out", str(output)])
    _enumerate_grid(args)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["candidate_count"] == 4
    assert result["claim_status"] == "ENUMERATION_ONLY_NOT_RUN"


def test_standalone_monthly_score_never_claims_calibration_from_two_rows(tmp_path):
    source = tmp_path / "comparison.csv"
    output = tmp_path / "score.json"
    source.write_text("measured,simulated\n100,100\n100,100\n", encoding="utf-8")
    args = build_parser().parse_args(
        ["score", "--csv", str(source), "--interval", "monthly", "--out", str(output)]
    )
    _score(args)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["metric_threshold_passes"] is True
    assert result["minimum_complete_month_count_passes"] is False
    assert result["calibration_claim_eligible"] is False
    assert "passes" not in result
