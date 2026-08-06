"""Promote gates (Audit P0): held-out honesty, provisional rejection, coverage
smoke watermark, and DSM-outcome flag."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_APP = Path(__file__).resolve().parents[1]
_SCRIPTS = _APP / "scripts"
_ML = _APP / "ml"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ML))

from promote_hybrid_ship import (  # noqa: E402
    MIN_PAIRS,
    REJECTED_DSM_OUTCOME,
    SMOKE_ENV,
    SMOKE_WATERMARK,
    _heldout_has_facility_metrics,
    _reject_provisional_heldout,
    promote_hybrid,
)

_GOOD_BASE_HELDOUT = {"extra_trees": {"facility_kw_mae": 3.0, "facility_kw_rmse": 4.0}}
_GOOD_DELTA_HELDOUT = {"random_forest": {"mae_delta_kw": 0.4, "mae_delta_kw_peak": 0.6}}


def _write_minimal_cards(
    art: Path,
    *,
    heldout: dict | None = None,
    delta_heldout: dict | None = None,
    n_days: int = 3,
) -> None:
    art.mkdir(parents=True, exist_ok=True)
    (art / "real_baseline_15min_v1.joblib").write_bytes(b"stub")
    (art / "eplus_delta_15min_v1.joblib").write_bytes(b"stub")
    base_card = {
        "champion": "extra_trees",
        "cv_teacher_forced": {"extra_trees": {"facility_kw_mae_peak_05_09": 1.0}},
    }
    if heldout is not None:
        base_card["cv_recursive_96_heldout"] = heldout
    (art / "real_baseline_15min_v1_model_card.json").write_text(
        json.dumps(base_card), encoding="utf-8"
    )
    delta_card = {
        "champion": "random_forest",
        "cv_teacher_forced": {"random_forest": {"mae_delta_kw_peak": 0.5}},
        "n_days": n_days,
    }
    if delta_heldout is not None:
        delta_card["cv_recursive_96_heldout"] = delta_heldout
    (art / "eplus_delta_15min_v1_model_card.json").write_text(
        json.dumps(delta_card), encoding="utf-8"
    )


def _patch_env(monkeypatch, tmp_path):
    """Point the site store at an empty dir so promote uses the fixture contract."""
    monkeypatch.setenv("LAKESIDE_SITE_ROOT", str(tmp_path / "site"))


def test_heldout_facility_metrics_helper():
    assert not _heldout_has_facility_metrics({})
    assert not _heldout_has_facility_metrics(None)
    assert not _heldout_has_facility_metrics({"note": "insufficient_heldout_days"})
    assert not _heldout_has_facility_metrics({"status": "not_evaluated"})
    assert _heldout_has_facility_metrics({"facility_kw_mae": 1.2})
    assert _heldout_has_facility_metrics(
        {"extra_trees": {"facility_kw_mae": 1.2, "facility_kw_rmse": 2.0}}
    )


@pytest.mark.parametrize(
    "held",
    [
        {"note": "provisional_from_teacher_forced_until_notebook_retrain"},
        {"extra_trees": {"facility_kw_mae": 1.0, "note": "teacher_forced"}},
        {"status": "not_evaluated"},
        {"note": "in_sample_first_day"},
        {"note": "insufficient_heldout_days"},
    ],
)
def test_reject_provisional_heldout(held):
    with pytest.raises(ValueError):
        _reject_provisional_heldout(held, "baseline")


def test_promote_refuses_without_heldout_key(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(art, heldout=None, delta_heldout=_GOOD_DELTA_HELDOUT, n_days=20)
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="cv_recursive_96_heldout"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_refuses_empty_heldout(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(art, heldout={}, delta_heldout=_GOOD_DELTA_HELDOUT, n_days=20)
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="cv_recursive_96_heldout"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_rejects_provisional_baseline(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(
        art,
        heldout={"note": "provisional_from_teacher_forced"},
        delta_heldout=_GOOD_DELTA_HELDOUT,
        n_days=20,
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)
    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="forbidden note/status"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_rejects_provisional_delta(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(
        art,
        heldout=_GOOD_BASE_HELDOUT,
        delta_heldout={"random_forest": {"mae_delta_kw": 0.4, "note": "teacher_forced"}},
        n_days=20,
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)
    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="delta.*forbidden note/status"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_refuses_missing_delta_heldout(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(art, heldout=_GOOD_BASE_HELDOUT, delta_heldout=None, n_days=20)
    monkeypatch.delenv(SMOKE_ENV, raising=False)
    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="delta model card missing"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_refuses_low_pair_count_without_smoke(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    assert MIN_PAIRS == 12
    _write_minimal_cards(
        art,
        heldout=_GOOD_BASE_HELDOUT,
        delta_heldout=_GOOD_DELTA_HELDOUT,
        n_days=3,
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match=rf"MIN_PAIRS={MIN_PAIRS}"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)
        with pytest.raises(ValueError, match=SMOKE_ENV):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def _fake_rollout(summary: dict):
    def _inner(models, contract):
        return {"contract_version": "hybrid_dsm_96_v1", "steps": [], "summary": dict(summary)}

    return _inner


def test_promote_smoke_sets_watermark(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(
        art,
        heldout=_GOOD_BASE_HELDOUT,
        delta_heldout=_GOOD_DELTA_HELDOUT,
        n_days=3,  # < MIN_PAIRS -> smoke path
    )
    monkeypatch.setenv(SMOKE_ENV, "1")
    _patch_env(monkeypatch, tmp_path)
    summary = {"delta_peak_kw": -1.0, "delta_kwh": -10.0, "peak_kw_baseline": 30.0}

    with patch("promote_hybrid_ship.load_joblib_model") as load, patch(
        "promote_hybrid_ship.rollout_96", _fake_rollout(summary)
    ):
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        out = promote_hybrid(artifacts=art, desktop_artifacts=desk)

    ship = json.loads((desk / "hybrid_ship_manifest.json").read_text(encoding="utf-8"))
    assert ship["ship_mode"] == "smoke_artifact"
    assert ship["watermark"] == SMOKE_WATERMARK
    assert SMOKE_WATERMARK in ship["honesty_note"]
    assert out["result"].get("outcome_flag") is None


def test_promote_flags_rejected_dsm_outcome(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(
        art,
        heldout=_GOOD_BASE_HELDOUT,
        delta_heldout=_GOOD_DELTA_HELDOUT,
        n_days=20,  # >= MIN_PAIRS -> no smoke needed
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)
    _patch_env(monkeypatch, tmp_path)
    # DSM worsens peak -> reject
    summary = {"delta_peak_kw": 1.5, "delta_kwh": 20.0}

    with patch("promote_hybrid_ship.load_joblib_model") as load, patch(
        "promote_hybrid_ship.rollout_96", _fake_rollout(summary)
    ):
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        out = promote_hybrid(artifacts=art, desktop_artifacts=desk)

    ship = json.loads((desk / "hybrid_ship_manifest.json").read_text(encoding="utf-8"))
    assert ship["ship_mode"] == "hybrid_96"
    assert ship["outcome_flag"] == REJECTED_DSM_OUTCOME
    assert out["result"]["outcome_flag"] == REJECTED_DSM_OUTCOME


def test_promote_flags_rejected_on_high_kwh(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(
        art,
        heldout=_GOOD_BASE_HELDOUT,
        delta_heldout=_GOOD_DELTA_HELDOUT,
        n_days=20,
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)
    _patch_env(monkeypatch, tmp_path)
    summary = {"delta_peak_kw": -1.0, "delta_kwh": 600.0}  # > 500 -> reject

    with patch("promote_hybrid_ship.load_joblib_model") as load, patch(
        "promote_hybrid_ship.rollout_96", _fake_rollout(summary)
    ):
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        out = promote_hybrid(artifacts=art, desktop_artifacts=desk)
    assert out["result"]["outcome_flag"] == REJECTED_DSM_OUTCOME
