from __future__ import annotations

from eplus_gym.mega.hp67_two_pass import patch_pass1_autosize, patch_pass2_hardsize


def test_pass1_sets_capacity_and_autosize():
    from pathlib import Path

    app = Path(__file__).resolve().parents[1]
    idf = app / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    text, patches = patch_pass1_autosize(idf.read_text(encoding="utf-8", errors="replace"), sensitivity="base")
    assert len(patches) == 9
    assert "Autosize" in text
    assert patches[0]["capacity_sensitivity"] == "base"


def test_pass2_requires_eio_fields():
    from pathlib import Path

    app = Path(__file__).resolve().parents[1]
    idf = app / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    pass1, _ = patch_pass1_autosize(idf.read_text(encoding="utf-8", errors="replace"))
    try:
        patch_pass2_hardsize(pass1, eio_text="", sensitivity="base")
    except ValueError as exc:
        assert "EIO" in str(exc) or "missing" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for empty EIO")
