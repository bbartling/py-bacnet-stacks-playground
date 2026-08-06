"""Promote gates: held-out recursive key + MIN_PAIRS (Audit P0)."""
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
    SMOKE_ENV,
    _heldout_has_facility_metrics,
    promote_hybrid,
)


def _write_minimal_cards(art: Path, *, heldout: dict | None, n_days: int = 3) -> None:
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
    (art / "eplus_delta_15min_v1_model_card.json").write_text(
        json.dumps(
            {
                "champion": "random_forest",
                "cv_teacher_forced": {"random_forest": {"mae_delta_kw_peak": 0.5}},
                "n_days": n_days,
            }
        ),
        encoding="utf-8",
    )


def test_heldout_facility_metrics_helper():
    assert not _heldout_has_facility_metrics({})
    assert not _heldout_has_facility_metrics(None)
    assert not _heldout_has_facility_metrics({"note": "insufficient_heldout_days"})
    assert _heldout_has_facility_metrics({"facility_kw_mae": 1.2})
    assert _heldout_has_facility_metrics(
        {"extra_trees": {"facility_kw_mae": 1.2, "facility_kw_rmse": 2.0}}
    )


def test_promote_refuses_without_heldout_key(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(art, heldout=None, n_days=20)
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="cv_recursive_96_heldout"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_refuses_empty_heldout(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    _write_minimal_cards(art, heldout={}, n_days=20)
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match="cv_recursive_96_heldout"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)


def test_promote_refuses_low_pair_count_without_smoke(tmp_path, monkeypatch):
    art = tmp_path / "art"
    desk = tmp_path / "desk"
    assert MIN_PAIRS == 12
    _write_minimal_cards(
        art,
        heldout={"extra_trees": {"facility_kw_mae": 3.0, "facility_kw_rmse": 4.0}},
        n_days=3,
    )
    monkeypatch.delenv(SMOKE_ENV, raising=False)

    with patch("promote_hybrid_ship.load_joblib_model") as load:
        load.return_value = (MagicMock(), ["a"], ["facility_kw"])
        with pytest.raises(ValueError, match=rf"MIN_PAIRS={MIN_PAIRS}"):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)
        with pytest.raises(ValueError, match=SMOKE_ENV):
            promote_hybrid(artifacts=art, desktop_artifacts=desk)
