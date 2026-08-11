"""Tests for fail-closed TrainingProfile."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(_ML))

from training_profile import (  # noqa: E402
    TrainingProfile,
    assert_desktop_library_allowed,
    require_profile,
)


def test_from_mode_smoke():
    p = TrainingProfile.from_mode("smoke")
    assert p.max_days == 36
    assert p.watermark == "SMOKE_ONLY"
    assert not p.allow_desktop_library_export


def test_from_mode_full_evaluation():
    p = TrainingProfile.from_mode("full_evaluation")
    assert p.max_days is None
    assert p.watermark is None
    assert not p.allow_desktop_library_export


def test_from_mode_full_deployment():
    p = TrainingProfile.from_mode("full_deployment")
    assert p.max_days is None
    assert p.watermark == "DEPLOYMENT_REFIT"
    assert p.allow_desktop_library_export


def test_require_profile_fail_closed(monkeypatch):
    monkeypatch.delenv("VIBE22_TRAINING_PROFILE", raising=False)
    with pytest.raises(ValueError, match="TrainingProfile required"):
        require_profile(None)
    monkeypatch.setenv("VIBE22_TRAINING_PROFILE", "smoke")
    assert require_profile(None).mode == "smoke"
    assert require_profile("full_evaluation").mode == "full_evaluation"


def test_desktop_export_refused_on_smoke():
    with pytest.raises(PermissionError, match="full_deployment"):
        assert_desktop_library_allowed(TrainingProfile.from_mode("smoke"))
    assert_desktop_library_allowed(TrainingProfile.from_mode("full_deployment"))
