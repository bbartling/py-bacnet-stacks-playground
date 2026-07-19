"""Tests for the cache-aware scenario runner (no Docker required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import wattlab.energyplus.runner as runner_module
from wattlab.energyplus.runner import (
    COMPLETE_MARKER,
    run_scenario,
    scenario_cache_key,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TINY_IDF = FIXTURES / "tiny_capacity.idf"

_TBL_CSV = """\
,Total Site Energy,100.0,500.0
,Total Building Area,1000.0
,Total End Uses,80.0,20.0
"""
_END_OK = "EnergyPlus Completed Successfully-- 2 Warning; 0 Severe Errors\n"


@pytest.fixture()
def epw(tmp_path: Path) -> Path:
    p = tmp_path / "weather.epw"
    p.write_text("LOCATION,Fixture City,IL,USA,TMY3,725300,41.98,-87.92,-6.0,201.0\n")
    return p


def _install_fake_simulate(monkeypatch, err_fixture: str = "err_success_warnings.err"):
    calls: list[dict] = []
    err_text = (FIXTURES / err_fixture).read_text(encoding="utf-8")

    def fake_simulate(idf: Path, epw: Path, output_dir: Path, **kwargs) -> dict:
        calls.append({"idf": str(idf), "epw": str(epw), "out": str(output_dir)})
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "eplustbl.csv").write_text(_TBL_CSV, encoding="utf-8")
        (output_dir / "eplusout.end").write_text(_END_OK, encoding="utf-8")
        (output_dir / "eplusout.err").write_text(err_text, encoding="utf-8")
        return {"returncode": 0, "ok": True, "output_dir": str(output_dir)}

    monkeypatch.setattr(runner_module, "simulate", fake_simulate)
    return calls


def test_cache_key_is_deterministic(epw: Path) -> None:
    patches = [{"name": "chiller_lockout", "params": {"oat_lockout_f": 55.0}}]
    k1 = scenario_cache_key(TINY_IDF, epw, patches)
    k2 = scenario_cache_key(TINY_IDF, epw, patches)
    assert k1 == k2
    assert len(k1) == 64

    # Any input change moves the key.
    assert scenario_cache_key(TINY_IDF, epw, []) != k1
    assert (
        scenario_cache_key(
            TINY_IDF, epw, [{"name": "chiller_lockout", "params": {"oat_lockout_f": 60.0}}]
        )
        != k1
    )
    other_epw = epw.parent / "other.epw"
    other_epw.write_text("LOCATION,Other City\n")
    assert scenario_cache_key(TINY_IDF, other_epw, patches) != k1


def test_patch_spec_normalization_equivalence(epw: Path) -> None:
    assert scenario_cache_key(TINY_IDF, epw, ["sat_reset"]) == scenario_cache_key(
        TINY_IDF, epw, [{"name": "sat_reset", "params": {}}]
    )


def test_dry_run_plans_without_simulating(tmp_path: Path, epw: Path, monkeypatch) -> None:
    calls = _install_fake_simulate(monkeypatch)
    plan = run_scenario(
        TINY_IDF,
        epw,
        tmp_path / "run",
        patches=[{"name": "outdoor_air_fraction", "params": {"min_oa_fraction": 0.5}}],
        dry_run=True,
    )
    assert plan["dry_run"] is True
    assert plan["steps"][0]["name"] == "outdoor_air_fraction"
    assert plan["steps"][-1]["step"] == "simulate"
    assert plan["cache_key"] == scenario_cache_key(
        TINY_IDF,
        epw,
        [{"name": "outdoor_air_fraction", "params": {"min_oa_fraction": 0.5}}],
    )
    assert calls == []
    assert not (tmp_path / "run").exists()


def test_run_scenario_simulates_and_writes_manifest(
    tmp_path: Path, epw: Path, monkeypatch
) -> None:
    calls = _install_fake_simulate(monkeypatch)
    out_dir = tmp_path / "run"
    report = run_scenario(
        TINY_IDF,
        epw,
        out_dir,
        patches=[{"name": "outdoor_air_fraction", "params": {"min_oa_fraction": 0.5}}],
    )

    assert len(calls) == 1
    assert report["status"] == "COMPLETE"
    assert report["cache_hit"] is False
    assert report["patches"][0]["patch"] == "outdoor_air_fraction"
    # Patched IDF (not the source) was simulated.
    assert calls[0]["idf"].endswith("patched_00_outdoor_air_fraction.idf")
    assert report["annual"]["electricity_kwh_year"] == pytest.approx(80 * 277.7777777778, rel=1e-6)

    manifest_path = out_dir / "run_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["cache_key"] == report["cache_key"]
    assert manifest["status"] == "COMPLETE"
    assert manifest["err_summary"]["severe"] == 0
    assert manifest["model_sha256"]
    assert report["result_record"]["err_summary"]["warnings"] == 2


def test_cache_hit_skips_simulation(tmp_path: Path, epw: Path, monkeypatch) -> None:
    calls = _install_fake_simulate(monkeypatch)
    cache_dir = tmp_path / "cache"
    patches = [{"name": "sat_reset", "params": {}}]

    first = run_scenario(
        TINY_IDF, epw, tmp_path / "run1", patches=patches, cache_dir=cache_dir
    )
    assert first["cache_hit"] is False
    assert len(calls) == 1
    marker = cache_dir / first["cache_key"] / COMPLETE_MARKER
    assert marker.is_file()
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "COMPLETE"

    second = run_scenario(
        TINY_IDF, epw, tmp_path / "run2", patches=patches, cache_dir=cache_dir
    )
    assert second["cache_hit"] is True
    assert len(calls) == 1  # no re-simulation
    assert second["status"] == "COMPLETE"
    assert second["cache_key"] == first["cache_key"]
    assert second["annual"]["electricity_kwh_year"] == first["annual"][
        "electricity_kwh_year"
    ]
    assert (tmp_path / "run2" / "run_manifest.json").is_file()


def test_severe_errors_mark_results_suspect(
    tmp_path: Path, epw: Path, monkeypatch
) -> None:
    _install_fake_simulate(monkeypatch, err_fixture="err_severe_completed.err")
    report = run_scenario(TINY_IDF, epw, tmp_path / "run")
    assert report["status"] == "RESULTS_SUSPECT"
    assert report["err"]["severe"] == 2
    assert "energyplus_severe_errors" in report["result_record"]["quality_flags"]
    assert report["result_record"]["status"] == "RESULTS_SUSPECT"


def test_failed_simulation_is_model_run_failed(
    tmp_path: Path, epw: Path, monkeypatch
) -> None:
    def failing_simulate(idf: Path, epw_path: Path, output_dir: Path, **kwargs) -> dict:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return {"returncode": 1, "ok": False, "output_dir": str(output_dir)}

    monkeypatch.setattr(runner_module, "simulate", failing_simulate)
    cache_dir = tmp_path / "cache"
    report = run_scenario(TINY_IDF, epw, tmp_path / "run", cache_dir=cache_dir)
    assert report["status"] == "MODEL_RUN_FAILED"
    # Failed runs never write a completion marker.
    assert not (cache_dir / report["cache_key"] / COMPLETE_MARKER).exists()
