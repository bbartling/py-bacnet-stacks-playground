"""Discover publishable artifacts under the site for Streamlit pickers.

Streamlit only **selects** paths agents already wrote — never runs EnergyPlus.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lakeside.paths import pinned_eplus_models_dir, resolve_eplus_model, site_root


@dataclass(frozen=True)
class PickerSelection:
    """Runtime picker state (paths absolute)."""

    idf_name: str
    idf_path: Path | None
    campus_json: Path | None
    bas_demand_csv: Path | None
    model_catalog_id: str | None = None


def list_idf_pins(site: Path | None = None) -> list[str]:
    """IDF filenames from repo pins + site eplus/models (unique, sorted)."""
    site = Path(site or site_root())
    names: set[str] = set()
    for folder in (pinned_eplus_models_dir(), site / "eplus" / "models"):
        if not folder.is_dir():
            continue
        for p in folder.glob("*.idf"):
            names.add(p.name)
    return sorted(names)


def list_campus_jsons(site: Path | None = None) -> list[Path]:
    site = Path(site or site_root())
    out: list[Path] = []
    for folder in (site / "utilities", site / "uploads" / "energy", site / "uploads"):
        if not folder.is_dir():
            continue
        out.extend(sorted(folder.glob("**/campus*.json")))
    # de-dupe
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def list_interval_csvs(site: Path | None = None) -> list[Path]:
    """Candidate Actual/interval demand CSVs (BAS×OAT or raw interval)."""
    site = Path(site or site_root())
    cands: list[Path] = []
    for folder in (site / "reports", site / "utilities", site / "clean_data"):
        if not folder.is_dir():
            continue
        for pat in (
            "*demand*weather*.csv",
            "*demand*hourly*.csv",
            "demand_interval*.csv",
            "*interval*kw*.csv",
        ):
            cands.extend(folder.rglob(pat))
    seen: set[str] = set()
    out: list[Path] = []
    for p in sorted(cands, key=lambda x: str(x)):
        key = str(p.resolve())
        if key in seen or not p.is_file():
            continue
        seen.add(key)
        out.append(p)
    return out


def list_bill_csvs_near(campus_json: Path) -> list[Path]:
    return sorted(campus_json.parent.glob("*.csv"))


def resolve_idf(name: str) -> Path | None:
    try:
        p = resolve_eplus_model(name)
        return p if p.is_file() else None
    except Exception:  # noqa: BLE001
        return None
