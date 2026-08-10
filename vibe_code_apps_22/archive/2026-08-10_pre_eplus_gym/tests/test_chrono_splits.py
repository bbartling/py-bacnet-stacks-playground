"""Unit tests for chronological (leakage-safe) split manifests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from chrono_splits import (  # noqa: E402
    build_split_manifest,
    is_heating_day,
    write_manifest,
)


def _make_day(day: str, month: int, oat_base: float) -> pd.DataFrame:
    steps = np.arange(96)
    oat = oat_base + 6.0 * np.sin(2 * np.pi * steps / 96.0)
    return pd.DataFrame(
        {
            "day": day,
            "month": month,
            "step_15": steps,
            "oat_f": oat,
        }
    )


def _winter_frame(n_days: int = 40, oat_base: float = 25.0) -> pd.DataFrame:
    days = pd.date_range("2026-01-01", periods=n_days, freq="D")
    frames = [
        _make_day(str(d.date()), int(d.month), oat_base + (i % 5)) for i, d in enumerate(days)
    ]
    return pd.concat(frames, ignore_index=True)


def test_is_heating_day_rule():
    # cold day: mean oat well below 50 -> heating
    assert is_heating_day(np.full(96, 20.0))
    # mild-but-cold-enough via degree-hours: mean above 50 but big deficit swings
    borderline = np.where(np.arange(96) < 48, 30.0, 72.0)
    assert is_heating_day(borderline)
    # warm day: no heating
    assert not is_heating_day(np.full(96, 70.0))
    # empty / all-nan is not heating
    assert not is_heating_day(np.array([np.nan, np.nan]))


def test_manifest_structure_and_chronology():
    df = _winter_frame(40)
    man = build_split_manifest(df)

    assert man["schema"] == "chrono_split_manifest_v1"
    assert man["n_days_total"] == 40
    # all days chronologically sorted
    assert man["all_days"] == sorted(man["all_days"])
    # cold winter frame -> all heating days
    assert man["n_heating_days"] == 40
    assert man["non_heating_days"] == []


def test_final_test_is_winter_tail_and_disjoint():
    df = _winter_frame(40)
    man = build_split_manifest(df)
    final = man["final_winter_test"]
    dev = man["dev_days"]

    assert final, "expected a non-empty final winter test block"
    # ~15% of 40 winter heating days
    assert len(final) == pytest.approx(round(0.15 * 40), abs=1)
    # final test is the chronological tail
    assert final == man["heating_days"][-len(final):]
    # dev and final are disjoint
    assert set(dev).isdisjoint(set(final))
    assert set(dev) | set(final) == set(man["heating_days"])


def test_folds_are_expanding_and_embargoed():
    df = _winter_frame(40)
    man = build_split_manifest(df)
    folds = man["folds"]
    dev = man["dev_days"]
    dev_index = {d: i for i, d in enumerate(dev)}

    assert len(folds) >= 2
    prev_train_len = -1
    for fold in folds:
        train, val, embargo = fold["train"], fold["val"], fold["embargo"]
        assert train and val
        # no leakage: every train day strictly precedes every val day
        max_train = max(dev_index[d] for d in train)
        min_val = min(dev_index[d] for d in val)
        assert max_train < min_val
        # expanding origin: train grows each fold
        assert len(train) > prev_train_len
        prev_train_len = len(train)
        # embargo gap sits between train end and val start
        if embargo:
            for e in embargo:
                assert max_train < dev_index[e] < min_val
        # val is contiguous
        val_idx = sorted(dev_index[d] for d in val)
        assert val_idx == list(range(val_idx[0], val_idx[0] + len(val_idx)))


def test_fallback_when_few_winter_days():
    # heating days but not enough dedicated {12,1,2} winter days -> fallback tail
    days = pd.date_range("2026-03-01", periods=25, freq="D")  # March = not winter month
    frames = [_make_day(str(d.date()), int(d.month), 22.0) for d in days]
    df = pd.concat(frames, ignore_index=True)
    man = build_split_manifest(df)
    assert man["n_heating_days"] == 25
    # fallback = last 20 heating days
    assert len(man["final_winter_test"]) == 20
    assert man["final_winter_test"] == man["heating_days"][-20:]


def test_write_manifest_roundtrip(tmp_path):
    df = _winter_frame(20)
    man = build_split_manifest(df)
    path = write_manifest(tmp_path / "eval" / "manifest.json", man)
    assert path.is_file()
    import json

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["schema"] == man["schema"]
    assert loaded["folds"] == man["folds"]
