"""Pin Lakeside A04 champion + site EPW (no eplus_gym_app)."""
from __future__ import annotations

import hashlib
from pathlib import Path

A04_IDF_NAME = "lakeside_w2a_a04_dual_champion.idf"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_site_epw(site: Path) -> Path:
    """Site AMY EPW without implying the campaign IDF is A04."""
    weather = Path(site) / "eplus" / "weather"
    epws = sorted(weather.glob("*.epw")) if weather.is_dir() else []
    if not epws:
        raise FileNotFoundError(f"no EPW under {weather}")
    amy = [p for p in epws if "amy" in p.name.lower()]
    return amy[0] if amy else epws[0]


def resolve_a04_and_epw(site: Path) -> tuple[Path, Path]:
    site = Path(site)
    idf = site / "eplus" / "models" / A04_IDF_NAME
    if not idf.is_file():
        raise FileNotFoundError(f"A04 dual champion missing: {idf}")
    return idf, resolve_site_epw(site)
