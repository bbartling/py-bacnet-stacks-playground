from pathlib import Path

import pytest

from vibe23.grid import RLIB_ENERGYPLUS_PIN
from vibe23.rllib_adapter import UpstreamInspectionError, inspect_rllib_energyplus_checkout


def _fake_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "upstream"
    for relative in (
        "rleplus/env/energyplus.py",
        "rleplus/examples/amphitheater/env.py",
        "rleplus/train/rllib.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "rl-energyplus"\nversion = "0.11.0"\n', encoding="utf-8"
    )
    return root


def test_inspection_requires_exact_pin_and_records_limitation(tmp_path, monkeypatch):
    root = _fake_checkout(tmp_path)
    monkeypatch.setattr("vibe23.rllib_adapter._git_head", lambda _: RLIB_ENERGYPLUS_PIN)
    result = inspect_rllib_energyplus_checkout(root)
    assert result["commit"] == RLIB_ENERGYPLUS_PIN
    assert result["building59_runtime_status"].startswith("BLOCKED")
    assert "first actuator" in result["reviewed_limitation"]
    assert len(result["files"]) == 4


def test_inspection_rejects_revision_drift(tmp_path, monkeypatch):
    root = _fake_checkout(tmp_path)
    monkeypatch.setattr("vibe23.rllib_adapter._git_head", lambda _: "0" * 40)
    with pytest.raises(UpstreamInspectionError, match="Unreviewed"):
        inspect_rllib_energyplus_checkout(root)
