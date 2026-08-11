"""Tests for ship_best_to_desktop arm selection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ship_best_to_desktop import peak_mae_from_card, pick_best_arm, score_arm  # noqa: E402


def test_peak_mae_from_card_uses_champion_block():
    card = {
        "champion": "extra_trees",
        "cv_recursive_96_heldout": {
            "random_forest": {"facility_kw_mae_peak_05_09": 50.0},
            "extra_trees": {"facility_kw_mae_peak_05_09": 37.5},
        },
    }
    assert peak_mae_from_card(card) == pytest.approx(37.5)


def test_pick_best_prefers_lower_peak(tmp_path, monkeypatch):
    import ship_best_to_desktop as mod

    runs = tmp_path / "runs"
    monkeypatch.setattr(mod, "RUNS", runs)

    def _write(arm: str, peak: float, winter: bool):
        d = runs / arm
        d.mkdir(parents=True)
        (d / "result.json").write_text(
            json.dumps({"ok": True, "champion": "extra_trees", "winter_only": winter}),
            encoding="utf-8",
        )
        (d / "real_baseline_15min_v1.joblib").write_bytes(b"fake")
        card = {
            "champion": "extra_trees",
            "cv_recursive_96_heldout": {
                "extra_trees": {"facility_kw_mae_peak_05_09": peak},
            },
        }
        (d / "real_baseline_15min_v1_model_card.json").write_text(
            json.dumps(card), encoding="utf-8"
        )

    _write("sklearn_winter", 40.0, True)
    _write("sklearn_allyear", 29.0, False)
    winner = pick_best_arm()
    assert winner["arm"] == "sklearn_allyear"
    assert winner["peak_mae"] == pytest.approx(29.0)


def test_pick_best_winter_tiebreak(tmp_path, monkeypatch):
    import ship_best_to_desktop as mod

    runs = tmp_path / "runs"
    monkeypatch.setattr(mod, "RUNS", runs)

    for arm, winter in (("sklearn_winter", True), ("sklearn_allyear", False)):
        d = runs / arm
        d.mkdir(parents=True)
        (d / "result.json").write_text(
            json.dumps({"ok": True, "champion": "extra_trees", "winter_only": winter}),
            encoding="utf-8",
        )
        (d / "real_baseline_15min_v1.joblib").write_bytes(b"x")
        card = {
            "champion": "extra_trees",
            "cv_recursive_96_heldout": {
                "extra_trees": {"facility_kw_mae_peak_05_09": 30.0},
            },
        }
        (d / "real_baseline_15min_v1_model_card.json").write_text(
            json.dumps(card), encoding="utf-8"
        )

    assert pick_best_arm()["arm"] == "sklearn_winter"
