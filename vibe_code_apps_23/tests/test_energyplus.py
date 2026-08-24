import json

from vibe23.energyplus import energyplus_capability, inspect_energyplus_run


def test_energyplus_capability_is_honest_and_non_claiming():
    report = energyplus_capability(docker_image="definitely-not-a-real-vibe23-image")
    assert report.schema == "vibe23.energyplus_capability.v1"
    assert report.capability in {
        "READY_NATIVE",
        "READY_DOCKER",
        "BLOCKED_DOCKER_IMAGE_MISSING",
        "BLOCKED_ENGINE_UNAVAILABLE",
    }
    assert "cannot establish" in report.claim_boundary


def test_existing_energyplus_run_passes_only_with_complete_zero_severe_artifacts(tmp_path):
    idf = tmp_path / "model.idf"
    epw = tmp_path / "weather.epw"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    epw.write_text("LOCATION,fixture\n", encoding="utf-8")
    (tmp_path / "eplusout.err").write_text("Program Version,EnergyPlus, Version 26.1\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 3 Warning; 0 Severe Errors; Elapsed Time=00hr 00min\n",
        encoding="utf-8",
    )
    (tmp_path / "eplusout.csv").write_text("Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,1\n", encoding="utf-8")

    report = inspect_energyplus_run(tmp_path, idf=idf, epw=epw, energyplus_version="26.1")
    assert report["engine_smoke_status"] == "ENGINE_SMOKE_PASS"
    assert report["claim_status"] == "MODEL_SEED_EVIDENCE_ONLY"
    assert report["warning_count"] == 3
    assert report["input_hashes"]["idf_sha256"]
    assert report["artifact_hashes"]["eplusout.csv"]
    json.dumps(report)


def test_existing_energyplus_run_fails_closed_on_severe_or_missing_csv(tmp_path):
    (tmp_path / "eplusout.err").write_text("** Severe ** bad object\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 0 Warning; 1 Severe Errors; Elapsed Time=00hr 00min\n",
        encoding="utf-8",
    )
    report = inspect_energyplus_run(tmp_path)
    assert report["engine_smoke_status"] == "ENGINE_SMOKE_FAIL"
    assert report["claim_status"] == "MODEL_RUN_FAILED"
    assert report["severe_count"] == 1
    assert report["required_artifacts"]["eplusout.csv"] is False
