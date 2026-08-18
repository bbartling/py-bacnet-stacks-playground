"""Campaign preflight fail-closed reasons. No EnergyPlus."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eplus_gym.rl.campaign_preflight import PreflightError, dates_are_contiguous, preflight_campaign

APP = Path(__file__).resolve().parents[1]


def _ok_bundle(tmp_path: Path) -> dict:
    days = ["2025-12-08", "2025-12-09", "2025-12-10"]
    return {
        "days": days,
        "forecast_source": "PERFECT_EPISODE_FORECAST",
        "hourly_forecasts": {d: [-5.0] * 24 for d in days},
        "paired_baselines": {d: {"n_intervals": 96} for d in days},
        "idf_sha256": "abc",
        "verified_idf_sha256": "abc",
        "epw_sha256": "def",
        "verified_epw_sha256": "def",
        "tariff_status": "ILLUSTRATIVE",
        "reward_contract_version": "reward_v2",
        "control_contract_version": "control_contract_v2",
        "observation_contract_version": "observation_contract_v3",
        "action_contract_version": "ppo_action_contract_v2",
        "output_root": str(tmp_path / "fresh_out"),
    }


def _raises(bundle, match: str, tmp_path: Path | None = None) -> None:
    with pytest.raises(PreflightError, match=match):
        preflight_campaign(
            bundle,
            app_root=APP,
            require_verified_active=False,
            check_energyplus=False,
        )


def test_dates_are_contiguous_helper():
    assert dates_are_contiguous(["2025-12-08", "2025-12-09", "2025-12-10"])
    assert not dates_are_contiguous(["2025-12-08", "2025-12-10"])


def test_no_verified_active_model_fails_closed():
    with pytest.raises(PreflightError, match="no active verified model"):
        preflight_campaign(
            _ok_bundle(Path(".")),
            app_root=APP,
            require_verified_active=True,
            check_energyplus=False,
        )


def test_non_contiguous_episode_dates(tmp_path):
    b = _ok_bundle(tmp_path)
    b["days"] = ["2025-12-08", "2025-12-10"]
    _raises(b, "non-contiguous")


def test_missing_hourly_forecasts(tmp_path):
    b = _ok_bundle(tmp_path)
    b["hourly_forecasts"] = {}
    _raises(b, "missing hourly forecasts")


def test_missing_paired_baselines(tmp_path):
    b = _ok_bundle(tmp_path)
    b["paired_baselines"] = {}
    _raises(b, "missing paired baseline")


def test_hash_mismatch(tmp_path):
    b = _ok_bundle(tmp_path)
    b["verified_idf_sha256"] = "not-abc"
    _raises(b, "hash mismatch")


def test_missing_tariff_label(tmp_path):
    b = _ok_bundle(tmp_path)
    b["tariff_status"] = ""
    _raises(b, "tariff")


def test_legacy_reward_contract(tmp_path):
    b = _ok_bundle(tmp_path)
    b["reward_contract_version"] = "operator_pay_2x_v1"
    _raises(b, "legacy")


def test_missing_energyplus_executable(tmp_path, monkeypatch):
    b = _ok_bundle(tmp_path)

    def boom():
        raise FileNotFoundError("energyplus executable not found")

    monkeypatch.setattr("eplus_gym.energyplus_cli.energyplus_exe", boom)
    with pytest.raises(PreflightError, match="missing EnergyPlus"):
        preflight_campaign(b, app_root=APP, require_verified_active=False, check_energyplus=True)


def test_writable_output_collision(tmp_path):
    collide = tmp_path / "occupied"
    collide.mkdir()
    (collide / "x.txt").write_text("nope", encoding="utf-8")
    b = _ok_bundle(tmp_path)
    b["output_root"] = str(collide)
    _raises(b, "output collision")


def test_incomplete_resume_manifest(tmp_path):
    b = _ok_bundle(tmp_path)
    b["resume"] = True
    b["checkpoint_manifest"] = {"rng": 1}
    _raises(b, "incomplete checkpoint")


def test_happy_path_without_active_model(tmp_path):
    out = preflight_campaign(
        _ok_bundle(tmp_path),
        app_root=APP,
        require_verified_active=False,
        check_energyplus=False,
    )
    assert out["ok"] is True
    assert out["n_days"] == 3


def test_cli_preflight_exits_nonzero_today():
    import subprocess
    import sys

    stub = APP / "docs" / "audits" / "figures" / "vibe22_live_trackb_long_rl" / "empty_bundle.json"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(json.dumps({"days": ["2025-12-08"]}) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(APP / "scripts" / "vibe22_rl.py"), "preflight-campaign", "--bundle", str(stub)],
        cwd=str(APP),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "no active verified model" in (proc.stdout + proc.stderr)
