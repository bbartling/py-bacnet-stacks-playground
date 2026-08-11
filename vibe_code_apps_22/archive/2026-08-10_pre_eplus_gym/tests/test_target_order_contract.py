"""Frozen TARGET_COLS / output order contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from target_scaling import assert_target_cols  # noqa: E402


def test_canonical_seven_outputs():
    assert_target_cols(TARGET_COLS)
    assert TARGET_COLS[0] == "facility_kw"
    assert len(TARGET_COLS) == 7


def test_shipped_meta_target_order_if_present():
    for stem in ("real_baseline_15min_v1", "eplus_delta_15min_v1", "real_baseline_15min_torch_v1"):
        meta = _ML / "artifacts" / f"{stem}_feature_meta.json"
        if not meta.is_file():
            continue
        doc = json.loads(meta.read_text(encoding="utf-8"))
        cols = doc.get("target_cols")
        if cols:
            assert list(cols) == list(TARGET_COLS), stem
