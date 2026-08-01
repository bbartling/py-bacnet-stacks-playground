"""pack_pa_bundle size guard + file list."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VIBE21 = Path(__file__).resolve().parents[1]
_TOOLS = _VIBE21 / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def test_collect_files_includes_models_and_ml():
    import pack_pa_bundle as pack

    files = pack.collect_files(_VIBE21)
    arcs = {a for _, a in files}
    assert any(a.startswith("flask_app/models/") for a in arcs) or any(
        a.endswith("demand_hourly_v1.joblib") for a in arcs
    )
    assert "ml/feature_compile_dm.py" in arcs
    assert "ml/artifact_paths.py" in arcs


def test_pack_size_guard(tmp_path, monkeypatch):
    import pack_pa_bundle as pack

    # Tiny fake root with one small file
    root = tmp_path / "vibe"
    (root / "flask_app").mkdir(parents=True)
    (root / "flask_app" / "app.py").write_text("# stub\n", encoding="utf-8")
    (root / "ml").mkdir()
    (root / "ml" / "feature_compile_dm.py").write_text("FEATURE_COLS=[]\n", encoding="utf-8")
    monkeypatch.setattr(
        pack,
        "_INCLUDE",
        ["flask_app/app.py", "ml/feature_compile_dm.py"],
    )
    out = tmp_path / "ok.zip"
    pack.pack(root, out, force=False)
    assert out.is_file()

    # Force oversize by lowering cap
    monkeypatch.setattr(pack, "_MAX_BYTES", 10)
    out2 = tmp_path / "big.zip"
    with pytest.raises(SystemExit) as ei:
        pack.pack(root, out2, force=False)
    assert "100" in str(ei.value) or "exceeds" in str(ei.value).lower() or ei.value.code != 0
