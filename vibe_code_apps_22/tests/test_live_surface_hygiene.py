"""Guardrails: hybrid / greybox product surface stays in archive, not live."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ML = _ROOT / "ml"
_CONTRACTS = _ROOT / "contracts"
_AUDITS = _ROOT / "docs" / "audits"
_ARCH = _ROOT / "archive" / "2026-08-10_pre_eplus_gym"


def test_hybrid_contracts_not_live():
    assert not (_CONTRACTS / "hybrid_dsm_96_v1.json").is_file()
    assert not (_CONTRACTS / "hybrid_dsm_96_v2.json").is_file()
    assert (_ARCH / "contracts" / "hybrid_dsm_96_v1.json").is_file()
    assert (_ARCH / "contracts" / "hybrid_dsm_96_v2.json").is_file()


def test_hybrid_ml_helpers_archived():
    for name in (
        "simulation_contract.py",
        "notebook_plots.py",
        "feature_compile_15min.py",
        "hybrid_rollout.py",
        "greybox",
        "control_twin_lab",
    ):
        assert not (_ML / name).exists(), f"live ml still has archived surface: {name}"
    for name in (
        "simulation_contract.py",
        "notebook_plots.py",
        "feature_compile_15min.py",
    ):
        assert (_ARCH / "ml_modules" / name).is_file()


def test_live_audits_are_gym_or_plant_only():
    names = {p.name for p in _AUDITS.glob("*.md")}
    assert "eplus_gym_v1.md" in names
    assert "plant_point_candidates.md" in names
    banned = {
        "interval_semantics_audit.md",
        "simulation_root_cause_audit.md",
        "greybox_sensor_manifest.md",
        "lag_train_serve_parity.md",
    }
    assert not (names & banned)


def test_streamlit_app_uses_width_stretch():
    src = (_ROOT / "eplus_gym_app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "use_container_width" not in src
    assert 'width="stretch"' in src


def test_live_ml_keeps_farm_helpers():
    for name in (
        "interval15.py",
        "feature_compile_heating_dsm.py",
        "physics_families.py",
        "artifact_paths.py",
        "eplus_validation_contract.py",
    ):
        assert (_ML / name).is_file()
