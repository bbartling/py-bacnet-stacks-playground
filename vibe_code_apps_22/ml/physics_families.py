"""Physics-family labels for DSM farms (honesty gate).

STRUCTURAL_LOAD_DIAGNOSTIC — IdealLoads + fixed-COP paired farm (screening).
W2A_PHYSICAL_DSM — water-to-air plant twin path (A04 champion IDF as starting
point). Do not claim validated treatment effects until ΔP/Δpeak gates pass.
"""
from __future__ import annotations

from pathlib import Path

STRUCTURAL_LOAD_DIAGNOSTIC = "STRUCTURAL_LOAD_DIAGNOSTIC"
W2A_PHYSICAL_DSM = "W2A_PHYSICAL_DSM"

# Repo-pinned A04 champion — do not overwrite; use as W2A farm seed only.
A04_CHAMPION_IDF = Path(__file__).resolve().parents[1] / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
A04_SCORECARD = Path(__file__).resolve().parents[1] / "models" / "eplus" / "best_scorecard_a04_dual.json"


def resolve_w2a_dsm_seed() -> Path:
    """Return A04 champion path if present; raise if missing (fail closed)."""
    if not A04_CHAMPION_IDF.is_file():
        raise FileNotFoundError(
            f"W2A_PHYSICAL_DSM seed missing: {A04_CHAMPION_IDF} "
            "(do not invent IdealLoads as W2A)"
        )
    return A04_CHAMPION_IDF


def label_for_farm(*, ideal_loads: bool = True) -> str:
    return STRUCTURAL_LOAD_DIAGNOSTIC if ideal_loads else W2A_PHYSICAL_DSM
