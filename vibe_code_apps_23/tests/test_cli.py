from __future__ import annotations

import json
from pathlib import Path

from vibe23.cli import build_parser


def test_parser_exposes_residential_commands():
    help_text = build_parser().format_help()
    for command in (
        "residential-doctor",
        "residential-smoke",
        "residential-dr",
        "residential-grid",
        "residential-battery-grid",
        "residential-report",
        "enumerate-grid",
        "inspect-tariff",
        "energyplus-doctor",
        "run-eplus-smoke",
        "inspect-eplus-run",
    ):
        assert command in help_text
    assert "download" not in help_text
    assert "plot-calibration" not in help_text


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
    from vibe23.cli import _enumerate_grid

    args = build_parser().parse_args(["enumerate-grid", "--grid", str(source), "--out", str(output)])
    _enumerate_grid(args)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["candidate_count"] == 4
    assert result["claim_status"] == "ENUMERATION_ONLY_NOT_RUN"


def test_package_metadata_is_residential():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert 'name = "vibe23-residential-dsm"' in text
