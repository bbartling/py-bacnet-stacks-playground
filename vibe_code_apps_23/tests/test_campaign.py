import pytest

from vibe23.campaign import (
    MAX_CAMPAIGN_RUNS,
    CampaignError,
    CampaignManifest,
    CampaignRunSpec,
    admit_energyplus_run,
    append_campaign_log,
    select_champion,
    validate_run_spec,
)


def _hashes():
    return {
        "idf_sha256": "a" * 64,
        "epw_sha256": "b" * 64,
        "source_data_sha256": "c" * 64,
        "point_map_sha256": "d" * 64,
        "calibration_contract_sha256": "e" * 64,
    }


def _manifest():
    return CampaignManifest("b59-2019", ("schedules", "lighting"), _hashes())


def _spec(manifest, ordinal=1, **kwargs):
    return CampaignRunSpec(
        manifest.manifest_sha256, ordinal, None, kwargs.pop("families", ("schedules",)),
        kwargs.pop("values", {"weekday_start_hour": 7}), kwargs.pop("hypothesis", "Adjust evidenced weekday start."), _hashes()
    )


def _diagnostics():
    return {
        "engine_smoke_passed": True,
        "process_returncode": 0,
        "warning_count": 0,
        "severe_count": 0,
        "fatal_count": 0,
        "required_evidence": {"end": True, "csv": True},
        "input_hashes": {"idf_sha256": "a" * 64, "epw_sha256": "b" * 64},
    }


def test_specs_are_deterministic_narrow_and_bound_to_declared_families():
    manifest = _manifest()
    spec = _spec(manifest)
    assert spec.candidate_id == _spec(manifest).candidate_id
    assert len(spec.cache_key) == 64
    validate_run_spec(spec, manifest)
    with pytest.raises(CampaignError, match="undeclared"):
        validate_run_spec(_spec(manifest, families=("hvac_efficiency",)), manifest)
    with pytest.raises(CampaignError, match="one or two"):
        _spec(manifest, families=("schedules", "lighting", "envelope"))


def test_campaign_hard_cap_is_fifty():
    with pytest.raises(CampaignError, match=str(MAX_CAMPAIGN_RUNS)):
        CampaignManifest("b59", ("schedules",), _hashes(), max_runs=MAX_CAMPAIGN_RUNS + 1)
    manifest = _manifest()
    with pytest.raises(CampaignError, match="cap"):
        validate_run_spec(_spec(manifest, ordinal=2), manifest, published_count=MAX_CAMPAIGN_RUNS)


def test_admission_rejects_dirty_or_unbound_energyplus_result():
    spec = _spec(_manifest())
    assert admit_energyplus_run(spec, _diagnostics()).admitted is True
    dirty = _diagnostics()
    dirty["severe_count"] = 1
    result = admit_energyplus_run(spec, dirty)
    assert result.admitted is False
    assert "severe_count_not_zero" in result.reasons


def test_append_only_hash_chained_log_and_gate_based_champion(tmp_path):
    manifest = _manifest()
    first = _spec(manifest)
    admission = admit_energyplus_run(first, _diagnostics())
    path = tmp_path / "campaign.jsonl"
    one = append_campaign_log(path, manifest=manifest, spec=first, admission=admission, metrics={"gl14_distance": 2.0}, gates={"monthly": True})
    second = _spec(manifest, ordinal=2, values={"weekday_start_hour": 8})
    two = append_campaign_log(path, manifest=manifest, spec=second, admission=admit_energyplus_run(second, _diagnostics()), metrics={"gl14_distance": 1.0}, gates={"monthly": True})
    assert two["previous_record_sha256"] == one["record_sha256"]
    champion = select_champion(path, required_metrics=("gl14_distance",), required_gates=("monthly",))
    assert champion["candidate_id"] == second.candidate_id
    with pytest.raises(CampaignError, match="already exists"):
        append_campaign_log(path, manifest=manifest, spec=first, admission=admission, metrics={"gl14_distance": 2.0}, gates={"monthly": True})


def test_champion_requires_explicit_metrics_and_gates(tmp_path):
    with pytest.raises(CampaignError, match="declared metrics and gates"):
        select_champion(tmp_path / "none.jsonl", required_metrics=(), required_gates=())
