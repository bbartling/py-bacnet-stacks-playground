"""Control Twin Lab V1 tests — A04 safety, provenance, archaeology fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP)]


def test_lab_stage_does_not_overwrite_champion(tmp_path):
    from control_twin_lab.seed import champion_sha256, stage_lab_idf
    from physics_families import A04_CHAMPION_IDF

    if not A04_CHAMPION_IDF.is_file():
        pytest.skip("A04 champion not in repo")
    before = champion_sha256()
    before_bytes = A04_CHAMPION_IDF.read_bytes()
    staged = stage_lab_idf(out_dir=tmp_path, steps_per_hour=6, tag="test")
    assert staged.is_file()
    assert staged.resolve() != A04_CHAMPION_IDF.resolve()
    assert A04_CHAMPION_IDF.read_bytes() == before_bytes
    assert champion_sha256() == before
    meta = (tmp_path / f"{staged.stem}_meta.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC_W2A_PROVENANCE" in meta
    assert "NON_PROMOTABLE" in meta


def test_surrogate_card_has_synthetic_provenance(tmp_path):
    from control_twin_lab.cases import smoke_cases
    from control_twin_lab.extract_plant import synthesize_plant_day
    from control_twin_lab.surrogate import train_surrogate, write_surrogate_card

    frames = [synthesize_plant_day(c) for c in smoke_cases()]
    _, card = train_surrogate(frames)
    assert card["provenance"] == "SYNTHETIC_W2A_PROVENANCE"
    assert card["promote"] == "NON_PROMOTABLE"
    assert "field" in card["note"].lower() or "NOT" in card["note"]
    out = tmp_path / "card.json"
    write_surrogate_card(out, card)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["honesty"] == "CONTROL_TWIN_LAB_V1"


def test_mine_plant_point_candidates_fixture(tmp_path):
    from mine_plant_point_candidates import mine, write_md

    site = tmp_path / "site"
    site.mkdir()
    fdd = site / "fdd_device_lookup.csv"
    pd.DataFrame(
        {
            "device_name": ["HP-1 Compressor Stage", "Loop Entering Water Temp", "Supply Fan Status"],
            "role": ["hp", "ewt", "fan"],
        }
    ).to_csv(fdd, index=False)
    rows = mine(site)
    by = {r["role"]: r for r in rows if r["status"] == "CANDIDATE"}
    assert "hp_enable_or_stage" in by
    assert by["hp_enable_or_stage"]["raw_name"]
    assert "invent" not in by["hp_enable_or_stage"]["raw_name"].lower()
    write_md(tmp_path / "c.md", rows, site)
    assert "CANDIDATE" in (tmp_path / "c.md").read_text(encoding="utf-8")


def test_mine_empty_site_documents_not_in_historian(tmp_path):
    from mine_plant_point_candidates import mine

    site = tmp_path / "empty_site"
    site.mkdir()
    rows = mine(site)
    assert all(r["status"] == "NOT_IN_HISTORIAN" for r in rows if r["status"] != "CANDIDATE_ALT")
    assert any(r["role"] == "loop_ewt" for r in rows)


def test_run_lab_smoke_fills_csvs(tmp_path):
    from control_twin_lab.runner import run_lab
    from physics_families import A04_CHAMPION_IDF

    if not A04_CHAMPION_IDF.is_file():
        pytest.skip("A04 champion not in repo")
    eplus = tmp_path / "eplus"
    ml = tmp_path / "ml"
    summary = run_lab(
        profile="smoke",
        out_dir=tmp_path / "lab",
        reports_eplus=eplus,
        reports_ml=ml,
    )
    assert summary["n_cases"] == 2
    assert summary["provenance"] == "SYNTHETIC_W2A_PROVENANCE"
    assert (eplus / "spinup_sensitivity.csv").is_file()
    assert (eplus / "timestep_sensitivity.csv").is_file()
    assert (ml / "dsm_treatment_scorecard.csv").is_file()
    card = json.loads((ml / "w2a_plant_electric_surrogate_card.json").read_text(encoding="utf-8"))
    assert card["promote"] == "NON_PROMOTABLE"
    spin = (eplus / "spinup_sensitivity.csv").read_text(encoding="utf-8")
    assert "pre_roll_days" in spin
    assert "GLHE" in spin or "glhe" in spin.lower() or "seasonal" in spin.lower()


def test_no_bacnet_write_in_control_twin_lab():
    root = _APP / "ml" / "control_twin_lab"
    forbidden = ("WriteProperty", "write_property", "bacnet_write")
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for tok in forbidden:
            assert tok not in text, f"{p}: {tok}"
