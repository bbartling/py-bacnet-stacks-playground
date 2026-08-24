import json

import pytest

from vibe23.model import (
    ModelEvidenceError,
    build_model_manifest,
    create_iteration_manifest,
    render_idf_seed,
    validate_parameter_ledger,
)


def _ledger():
    return {
        "schema": "vibe23.parameter_ledger.v1",
        "entries": [
            {
                "id": "A",
                "parameter_family": "schedules",
                "status": "ASSUMPTION",
                "value": 1,
                "units": "fraction",
                "source_ref": "test",
                "rationale": "test",
            }
        ],
    }


def test_ledger_reports_unresolved_and_blocks_freeze():
    ledger = _ledger()
    ledger["entries"][0]["status"] = "UNRESOLVED"
    assert validate_parameter_ledger(ledger)["model_freeze_eligible"] is False


def test_iteration_is_narrow_and_needs_all_hashes():
    hashes = {
        "idf_sha256": "a" * 64,
        "epw_sha256": "b" * 64,
        "source_data_sha256": "c" * 64,
        "point_map_sha256": "d" * 64,
        "parameter_ledger_sha256": "e" * 64,
    }
    manifest = create_iteration_manifest(
        iteration_id="I01",
        parent_iteration_id=None,
        changed_parameter_families=["schedules"],
        hypothesis="Correct the evidenced weekday schedule.",
        ledger=_ledger(),
        model_input_hashes=hashes,
    )
    assert manifest["claim_status"] == "CALIBRATION_IN_PROGRESS"
    with pytest.raises(ModelEvidenceError, match="one or two"):
        create_iteration_manifest(
            iteration_id="I02", parent_iteration_id="I01", changed_parameter_families=[], hypothesis="x", ledger=_ledger(), model_input_hashes=hashes
        )


def test_render_seed_fails_closed_for_unknown_or_unfilled_tokens(tmp_path):
    template = tmp_path / "seed.idf.template"
    template.write_text("Version, {{VERSION}}; Building, {{NAME}};", encoding="utf-8")
    with pytest.raises(ModelEvidenceError, match="unresolved"):
        render_idf_seed(template, tmp_path / "out.idf", {"VERSION": "24.2"})
    with pytest.raises(ModelEvidenceError, match="forbidden"):
        render_idf_seed(template, tmp_path / "out.idf", {"VERSION": "24.2\nBuilding,Injected", "NAME": "B59"})
    output = render_idf_seed(template, tmp_path / "out.idf", {"VERSION": "24.2", "NAME": "B59"})
    assert "{{" not in output.read_text(encoding="utf-8")


def test_model_manifest_hashes_all_required_inputs(tmp_path):
    paths = {}
    for name in ("idf", "epw", "data", "point_map"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        paths[name] = path
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(_ledger()), encoding="utf-8")
    manifest = build_model_manifest(
        idf_path=paths["idf"], epw_path=paths["epw"], source_data_manifest_path=paths["data"],
        point_map_path=paths["point_map"], parameter_ledger_path=ledger_path, energyplus_version="24.2"
    )
    assert set(manifest["input_hashes"]) == {"idf_sha256", "epw_sha256", "source_data_sha256", "point_map_sha256", "parameter_ledger_sha256"}
    assert manifest["claim_status"] == "CALIBRATION_BOOTSTRAP"
    assert manifest["energyplus_seed_gate"]["passes"] is False
