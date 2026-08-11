"""Delta champion must follow recursive peak MAE, not teacher-forced."""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from multioutput_families import pick_recursive_champion  # noqa: E402


def test_pick_recursive_not_tf_winner():
    families = ["tf_winner", "rec_winner", "other"]
    # TF would pick tf_winner; recursive picks rec_winner
    cv_rec = {
        "tf_winner": {"mae_delta_kw_peak": 40.0},
        "rec_winner": {"mae_delta_kw_peak": 10.0},
        "other": {"mae_delta_kw_peak": 25.0},
    }
    assert pick_recursive_champion(families, cv_rec, peak_key="mae_delta_kw_peak") == "rec_winner"


def test_pick_uses_facility_key_for_baseline():
    families = ["a", "b"]
    cv_rec = {
        "a": {"facility_kw_mae_peak_05_09": 12.0},
        "b": {"facility_kw_mae_peak_05_09": 8.0},
    }
    assert pick_recursive_champion(families, cv_rec) == "b"
