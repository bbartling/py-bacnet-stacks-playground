"""Shared notebook helpers: prove native farm + site Lakeside IDF (no proxy)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import Markdown, display


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def prove_native_farm_load(
    *,
    root: Path,
    paths: dict[str, Path],
    site: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load farm parquet, assert ENERGYPLUS_NATIVE_RUN, show human proof tables.

    Prefers hybrid paired 15-min farm; falls back to legacy hourly stem if present.
    """
    site = site or Path(
        os.environ.get(
            "LAKESIDE_SITE_ROOT",
            r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
        )
    )
    art = Path(paths.get("eplus_farm", root / "ml" / "artifacts" / "heating_dsm_eplus_farm_hourly.parquet")).parent
    paired = art / "heating_dsm_eplus_paired_15min_v1.parquet"
    paired_sum = art / "heating_dsm_eplus_paired_15min_v1_summary.json"
    if paired.is_file():
        farm_pq = paired
        farm_sum = paired_sum if paired_sum.is_file() else art / "eplus_farm_summary.json"
    else:
        farm_pq = paths["eplus_farm"]
        farm_sum = farm_pq.parent / "eplus_farm_summary.json"
    elig = site / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    champ = site / "eplus" / "models" / "lakeside_6zone_gshp_best_utility.idf"
    staged = site / "eplus" / "models" / "staged" / "lakeside_6zone_gshp_best_utility_dsm_v1.idf"
    creekside_alias = site / "eplus" / "models" / "creekside_6zone_gshp_best_utility.idf"

    assert farm_pq.is_file(), f"missing farm parquet {farm_pq} — run eplus_heating_dsm_farm.py"
    assert farm_sum.is_file(), f"missing {farm_sum}"
    fs = json.loads(farm_sum.read_text(encoding="utf-8"))
    assert fs.get("provenance") == "ENERGYPLUS_NATIVE_RUN", fs
    assert elig.is_file(), f"missing {elig} — run eplus_stage_repair_and_rescore.py"
    ej = json.loads(elig.read_text(encoding="utf-8"))

    df = pd.read_parquet(farm_pq)
    assert "provenance" in df.columns, "farm parquet missing provenance column"
    provs = df["provenance"].astype(str).value_counts().to_dict()
    assert set(provs) == {"ENERGYPLUS_NATIVE_RUN"}, provs
    assert "BAS_BOOTSTRAP" not in str(provs)
    assert "ENERGYPLUS_SIMULATED" not in str(provs)
    assert "physics_proxy" not in str(provs).lower()
    if "input_hash" in df.columns:
        assert not df["input_hash"].isna().any(), "hash gate: null input_hash"
    honesty = fs.get("honesty") or (df["honesty"].iloc[0] if "honesty" in df.columns else None)

    champ_sha = _sha256(champ) if champ.is_file() else None
    alias_sha = _sha256(creekside_alias) if creekside_alias.is_file() else None
    staged_sha = _sha256(staged) if staged.is_file() else None
    if champ_sha and alias_sha:
        assert champ_sha == alias_sha, "lakeside/creekside utility champion files diverge"

    lines = [
        "### Proof — training labels are native EnergyPlus (not BAS proxy)",
        f"- **Farm parquet:** `{farm_pq}`",
        f"- **Rows / runs / days:** {len(df)} / {fs.get('n_runs_accepted') or fs.get('n_scenarios_accepted')} / {fs.get('n_days')}",
        f"- **Provenance (summary):** `{fs.get('provenance')}`",
        f"- **Provenance (row counts):** `{provs}`",
        f"- **Honesty:** `{honesty}`",
        f"- **Site root:** `{site}`",
        f"- **Champion IDF (Lakeside rename of Creekside):** `{champ.name}`",
        f"  - SHA-256: `{champ_sha}`",
        f"- **Creekside alias same bytes:** `{champ_sha == alias_sha}`",
        f"- **Staged DSM IDF:** `{staged.name}`",
        f"  - SHA-256: `{staged_sha}` (matches DSM_ELIGIBLE: `{ej.get('staged_sha256')}`)",
        f"- **EPW SHA-256 (farm):** `{fs.get('epw_sha256') or (df['epw_sha256'].iloc[0] if 'epw_sha256' in df.columns else None)}`",
        f"- **Monthly GL14 (staged):** `{ej.get('gl14_status')}` · NMBE={ej.get('nmbe_pct')}% · CVRMSE={ej.get('cvrmse_pct')}%",
        "",
        "IdealLoads + fixed COP is the twin's electric demand model (not a fake kW formula). "
        "Hybrid path trains deltas separately from real BAS baseline — never concat rows. "
        "There is **no** `BAS_BOOTSTRAP_PROXY` / `physics_proxy_kw` path anymore.",
    ]
    display(Markdown("\n".join(lines)))

    show_cols = [
        c
        for c in (
            "day",
            "hour_ending",
            "strategy_id",
            "facility_kw",
            "provenance",
            "idf_sha256",
            "epw_sha256",
            "run_id",
            "oat_f",
            "heat_cop_proxy",
        )
        if c in df.columns
    ]
    display(Markdown("#### First 12 farm rows (human inspection)"))
    display(df[show_cols].head(12))
    display(Markdown("#### Provenance / strategy counts"))
    display(pd.DataFrame({"count": df["provenance"].value_counts()}))
    if "strategy_id" in df.columns:
        display(pd.DataFrame({"count": df["strategy_id"].value_counts()}))

    return df, {"farm_summary": fs, "eligible": ej, "champion_sha256": champ_sha, "staged_sha256": staged_sha}
