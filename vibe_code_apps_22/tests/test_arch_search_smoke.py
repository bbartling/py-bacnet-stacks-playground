"""Arch registry + one smoke search iter (limit 2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))
sys.path.insert(0, str(_APP / "scripts"))

from arch_registry import ITER_01, candidates_for_iter, mutate_for_next_iter  # noqa: E402


def test_iter01_has_ten():
    assert len(ITER_01) == 10
    assert any("phys_lstm" in c["name"] for c in ITER_01)


def test_mutate_produces_ten():
    fake = [{"name": c["name"], "pass": True, "score": float(i)} for i, c in enumerate(ITER_01)]
    nxt = mutate_for_next_iter(fake, iter_n=2)
    assert len(nxt) == 10
    assert all("__i02_" in c["name"] for c in nxt)


def test_arch_search_cli_smoke(tmp_path, monkeypatch):
    import arch_search_10x10 as mod

    monkeypatch.setattr(mod, "OUT_ROOT", tmp_path)
    rc = mod.main.__wrapped__ if hasattr(mod.main, "__wrapped__") else None
    # call via argv
    monkeypatch.setattr(
        sys,
        "argv",
        ["arch_search_10x10.py", "--iter", "1", "--limit", "2", "--out-root", str(tmp_path)],
    )
    assert mod.main() in (0, 1)
    board = tmp_path / "iter_01" / "leaderboard.json"
    assert board.is_file()
    doc = json.loads(board.read_text(encoding="utf-8"))
    assert doc["n"] == 2
