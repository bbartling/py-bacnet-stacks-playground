"""Model loader prefers flask_app/models/ for turnkey PA dumps."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VIBE21 = Path(__file__).resolve().parents[2]
_ML = _VIBE21 / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))
if str(_VIBE21) not in sys.path:
    sys.path.insert(0, str(_VIBE21))


def test_resolve_load_paths_prefers_flask_models():
    from artifact_paths import MODEL_STEM_V1, MODEL_STEM_V2, flask_models_dir, resolve_load_paths

    art, card = resolve_load_paths()
    flask_dir = flask_models_dir()
    for stem in (MODEL_STEM_V2, MODEL_STEM_V1):
        if (flask_dir / f"{stem}.joblib").is_file() and (flask_dir / f"{stem}_model_card.json").is_file():
            assert art == flask_dir / f"{stem}.joblib"
            assert card == flask_dir / f"{stem}_model_card.json"
            return
    pytest.skip("flask_app/models not populated")


def test_load_bundle_from_flask_models():
    from flask_app.model_loader import clear_bundle_cache, load_bundle
    from artifact_paths import flask_models_dir, MODEL_STEM_V1, MODEL_STEM_V2

    has = any((flask_models_dir() / f"{s}.joblib").is_file() for s in (MODEL_STEM_V2, MODEL_STEM_V1))
    if not has:
        pytest.skip("no bundled joblib")
    clear_bundle_cache()
    b = load_bundle()
    assert b["card"]["model_id"] in ("demand_hourly_v1", "demand_hourly_v2")
    assert "facility_kw" in str(b["card"].get("targets", []))
    assert Path(b["artifact_path"]).is_file()
