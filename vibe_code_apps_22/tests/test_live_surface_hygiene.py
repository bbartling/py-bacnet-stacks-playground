"""Guardrails: hybrid / greybox product surface stays in archive, not live."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ML = _ROOT / "ml"
_ARCH_ML = _ROOT / "archive" / "ml"
_CONTRACTS = _ROOT / "contracts"
_AUDITS = _ROOT / "docs" / "audits"
_ARCH = _ROOT / "archive" / "2026-08-10_pre_eplus_gym"


def test_hybrid_contracts_not_live():
    assert not (_CONTRACTS / "hybrid_dsm_96_v1.json").is_file()
    assert not (_CONTRACTS / "hybrid_dsm_96_v2.json").is_file()
    assert (_ARCH / "contracts" / "hybrid_dsm_96_v1.json").is_file()
    assert (_ARCH / "contracts" / "hybrid_dsm_96_v2.json").is_file()


def test_live_ml_package_is_gone():
    assert not _ML.exists(), "live ml/ must stay archived — use archive/ml helpers only"


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
    assert "IDF source" not in src
    assert "Lakeside DSM" in src
    assert "Farm month" not in src
    assert "_render_farm_diagnostic" not in src
    assert "Building and fuel" not in src


def test_archived_ml_keeps_eplus_helpers():
    for name in (
        "interval15.py",
        "feature_compile_heating_dsm.py",
        "physics_families.py",
        "artifact_paths.py",
        "eplus_validation_contract.py",
        "eplus_multires_metrics.py",
        "energy_math.py",
    ):
        assert (_ARCH_ML / name).is_file()
