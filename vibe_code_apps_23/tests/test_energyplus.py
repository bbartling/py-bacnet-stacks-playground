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


def test_existing_energyplus_run_passes_only_with_clean_complete_hashed_artifacts(tmp_path):
    idf = tmp_path / "model.idf"
    epw = tmp_path / "weather.epw"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    epw.write_text("LOCATION,fixture\n", encoding="utf-8")
    (tmp_path / "eplusout.err").write_text("Program Version,EnergyPlus, Version 26.1\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors; Elapsed Time=00hr 00min\n",
        encoding="utf-8",
    )
    (tmp_path / "eplusout.csv").write_text("Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,1\n", encoding="utf-8")
    (tmp_path / "console.log").write_text("EnergyPlus Completed Successfully.\n", encoding="utf-8")

    report = inspect_energyplus_run(
        tmp_path, idf=idf, epw=epw, energyplus_version="26.1", process_returncode=0
    )
    assert report["engine_smoke_status"] == "ENGINE_SMOKE_PASS"
    assert report["claim_status"] == "MODEL_SEED_EVIDENCE_ONLY"
    assert report["warning_count"] == 0
    assert report["warning_gate_passed"] is True
    assert report["input_hashes"]["idf_sha256"]
    assert report["artifact_hashes"]["eplusout.csv"]
    json.dumps(report)


def test_existing_energyplus_run_rejects_warnings_and_unknown_returncode(tmp_path):
    idf = tmp_path / "model.idf"
    epw = tmp_path / "weather.epw"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    epw.write_text("LOCATION,fixture\n", encoding="utf-8")
    (tmp_path / "eplusout.err").write_text("** Warning ** fixture warning\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors; Elapsed Time=00hr 00min\n",
        encoding="utf-8",
    )
    (tmp_path / "eplusout.csv").write_text(
        "Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,1\n", encoding="utf-8"
    )
    report = inspect_energyplus_run(tmp_path, idf=idf, epw=epw, energyplus_version="26.1")
    assert report["engine_smoke_status"] == "ENGINE_SMOKE_FAIL"
    assert report["warning_gate_passed"] is False
    assert report["required_evidence"]["process_returncode_zero"] is False


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
    assert report["required_evidence"]["eplusout.csv"] is False


def test_energyplus_gate_rejects_malformed_summary_and_facility_values(tmp_path):
    idf = tmp_path / "model.idf"
    epw = tmp_path / "weather.epw"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    epw.write_text("LOCATION,fixture\n", encoding="utf-8")
    (tmp_path / "eplusout.err").write_text("Program Version,EnergyPlus\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text("EnergyPlus Completed Successfully\n", encoding="utf-8")
    (tmp_path / "eplusout.csv").write_text(
        "Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,not-a-number\n", encoding="utf-8"
    )
    report = inspect_energyplus_run(
        tmp_path, idf=idf, epw=epw, energyplus_version="26.1", process_returncode=0
    )
    assert report["engine_smoke_passed"] is False
    assert report["required_evidence"]["end_summary_parseable"] is False
    assert report["csv_values_valid"] is False
    assert "nonnumeric" in report["csv_invalid_reason"]


def test_standalone_inspection_accepts_only_hash_bound_manifest_returncode(tmp_path):
    idf = tmp_path / "model.idf"
    epw = tmp_path / "weather.epw"
    idf.write_text("Version,26.1;\n", encoding="utf-8")
    epw.write_text("LOCATION,fixture\n", encoding="utf-8")
    (tmp_path / "eplusout.err").write_text("Program Version,EnergyPlus\n", encoding="utf-8")
    (tmp_path / "eplusout.end").write_text(
        "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors; Elapsed Time=00hr 00min\n",
        encoding="utf-8",
    )
    (tmp_path / "eplusout.csv").write_text(
        "Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,1\n", encoding="utf-8"
    )
    manifest = inspect_energyplus_run(
        tmp_path, idf=idf, epw=epw, energyplus_version="26.1", process_returncode=0
    )
    manifest["schema"] = "vibe23.energyplus_smoke_manifest.v1"
    manifest["selected_engine"] = "native"
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = inspect_energyplus_run(tmp_path, idf=idf, epw=epw, energyplus_version="26.1")
    assert report["engine_smoke_passed"] is True
    assert report["process_returncode_source"] == "hash_bound_run_manifest"

    wrong_version = inspect_energyplus_run(tmp_path, idf=idf, epw=epw, energyplus_version="bogus")
    assert wrong_version["engine_smoke_passed"] is False
    assert wrong_version["manifest_binding_valid"] is False

    (tmp_path / "eplusout.csv").write_text(
        "Date/Time,Electricity:Facility [J](Hourly)\n1/1 01:00,2\n", encoding="utf-8"
    )
    tampered = inspect_energyplus_run(tmp_path, idf=idf, epw=epw, energyplus_version="26.1")
    assert tampered["engine_smoke_passed"] is False
    assert tampered["manifest_binding_valid"] is False
