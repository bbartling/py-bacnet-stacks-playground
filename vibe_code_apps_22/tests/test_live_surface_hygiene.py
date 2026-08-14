"""Guardrails: RL-only live tree; rleplus backend; A04 champion; no Streamlit."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ML = _ROOT / "ml"
_HYBRID_ARCH = _ROOT / "archive" / "2026-08-10_pre_eplus_gym"
_A04 = "lakeside_w2a_a04_dual_champion.idf"


def test_hybrid_pre_eplus_gym_archive_purged():
    assert not _HYBRID_ARCH.exists(), "do not restore 2026-08-10_pre_eplus_gym into the tree"


def test_live_ml_package_is_gone():
    assert not _ML.exists()


def test_no_streamlit_in_active_tree():
    banned = ("import streamlit", "from streamlit")
    roots = (_ROOT / "eplus_gym", _ROOT / "scripts")
    skip_parts = {"archive", ".pytest_cache", "__pycache__", "examples", "third_party"}
    hits = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in skip_parts for part in path.parts):
                continue
            src = path.read_text(encoding="utf-8", errors="ignore")
            for ban in banned:
                if ban in src:
                    hits.append(f"{path.relative_to(_ROOT)}:{ban}")
    assert hits == [], f"streamlit still live: {hits}"


def test_cli_is_rl_only():
    assert (_ROOT / "scripts" / "vibe22_rl.py").is_file()
    assert not (_ROOT / "scripts" / "vibe22.py").is_file()
    assert not (_ROOT / "eplus_gym_app").exists()
    live_py = sorted(p.name for p in (_ROOT / "scripts").glob("*.py"))
    assert live_py == ["gate_six_zone_actuation.py", "vibe22_rl.py"]


def test_a04_champion_filename():
    from eplus_gym.envs.lakeside_w2a import A04_IDF_NAME, is_a04_idf_filename

    assert A04_IDF_NAME == _A04
    pinned = _ROOT / "models" / "eplus" / _A04
    assert pinned.is_file(), f"missing repo pin {pinned}"
    assert is_a04_idf_filename(f"staged_{_A04}")
    assert not is_a04_idf_filename("amphitheater.idf")


def test_rleplus_backend_importable():
    from eplus_gym.rleplus_path import find_rleplus_root

    root = find_rleplus_root()
    assert (root / "rleplus" / "env" / "energyplus.py").is_file()
    env_src = (_ROOT / "eplus_gym" / "env.py").read_text(encoding="utf-8")
    assert "self.action_space.sample" not in env_src
    assert "from rleplus.env.energyplus import" in env_src
