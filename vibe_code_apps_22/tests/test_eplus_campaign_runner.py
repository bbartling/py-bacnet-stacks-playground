"""Tests for real campaign runner status machine and promotion refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "archive" / "ml"))

from eplus_calibrate_multires import (  # noqa: E402
    EXECUTABLE_KNOBS,
    _bounded_executable_plan,
    _rank_candidate,
    _sensitivity_screen,
    execute_trial,
)
from eplus_multires_metrics import resolution_block  # noqa: E402

REGISTRY = json.loads(
    (_ROOT / "contracts" / "eplus_calib_param_registry_v1.json").read_text(encoding="utf-8")
)


def test_nonexecutable_params_rejected_not_planned():
    trials = _sensitivity_screen(REGISTRY, "A")
    rejected = [t for t in trials if t["status"] == "rejected"]
    planned = [t for t in trials if t["status"] == "planned"]
    assert rejected, "schedule/setpoint knobs without apply_knobs support must be rejected"
    assert all(t["param_id"] not in EXECUTABLE_KNOBS for t in rejected)
    assert all(t["param_id"] in EXECUTABLE_KNOBS for t in planned)


def test_planned_not_counted_as_succeeded_in_summary_shape():
    plan = _bounded_executable_plan(REGISTRY, max_trials=3)
    assert len(plan) == 3
    assert all(t["status"] == "planned" for t in plan)


def test_promotion_refused_when_hourly_fails():
    monthly = resolution_block([100] * 10, [101] * 10, resolution="monthly")
    interv = resolution_block([100] * 10, [101] * 10, resolution="monthly")
    hourly = resolution_block([50.0] * 50, [90.0] * 50, resolution="hourly")
    rank = _rank_candidate(monthly, interv, hourly)
    assert hourly["status"] == "fail"
    assert rank["chrono_val_hourly_status"] == "fail"


def test_execute_trial_failed_energyplus(tmp_path):
    idf = tmp_path / "parent.idf"
    idf.write_text("Version,22.2;\n", encoding="utf-8")
    epw = tmp_path / "w.epw"
    epw.write_text("epw", encoding="utf-8")
    camp = tmp_path / "camp"
    camp.mkdir()
    root = tmp_path / "site"
    root.mkdir()
    trial = {
        "trial_id": "B_lights_mult_lo",
        "knobs": {"lights_mult": 0.7},
        "param_id": "lights_mult",
        "stage": "B",
        "bound_label": "lo",
        "value": 0.7,
    }

    mock_manifest = MagicMock()
    mock_manifest.exit_code = 1
    mock_manifest.accepted = False
    mock_manifest.severe_count = 0
    mock_manifest.fatal_count = 1
    mock_manifest.reject_reasons = ["fatal"]
    mock_manifest.command = ["energyplus"]
    mock_manifest.runtime_sec = 0.1

    with patch("eplus_calibrate_multires.apply_knobs", return_value="Version,22.2;\n"):
        with patch("eplus_calibrate_multires.run_energyplus", return_value=mock_manifest):
            with patch("eplus_calibrate_multires.energyplus_version", return_value="mock"):
                with patch("eplus_calibrate_multires.sha256_file", return_value="abc"):
                    res = execute_trial(
                        root=root, camp=camp, parent_idf=idf, epw=epw, trial=trial
                    )
    assert res["status"] == "failed"
    assert (camp / "trials" / trial["trial_id"] / "trial_result.json").is_file()


def test_execute_trial_rejects_unsupported_knob(tmp_path):
    idf = tmp_path / "parent.idf"
    idf.write_text("Version,22.2;\n", encoding="utf-8")
    epw = tmp_path / "w.epw"
    epw.write_text("epw", encoding="utf-8")
    camp = tmp_path / "camp"
    camp.mkdir()
    res = execute_trial(
        root=tmp_path,
        camp=camp,
        parent_idf=idf,
        epw=epw,
        trial={
            "trial_id": "A_sched_occ_shift_h_lo",
            "knobs": {"sched_occ_shift_h": -2.0},
            "param_id": "sched_occ_shift_h",
            "stage": "A",
            "bound_label": "lo",
            "value": -2.0,
        },
    )
    assert res["status"] == "rejected"
