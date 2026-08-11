"""Resolve AMY vs Madison TMY EPWs. Never auto-pick Chicago screening as TMY."""
from __future__ import annotations

from pathlib import Path
from typing import Any

KIND_AMY = "AMY_OPEN_METEO"
KIND_TMY_MSN = "TMY_MSN"
KIND_TMY_SCREENING = "TMY_SCREENING"
KIND_UNKNOWN = "UNKNOWN"

_CHICAGO = ("chicago", "ohare", "725300")
_SCREENING = ("screening", "stand-in", "standin")


def classify_epw(path: Path | str | None) -> str:
    if path is None:
        return KIND_UNKNOWN
    name = Path(path).name.lower()
    if "amy" in name:
        return KIND_AMY
    if any(tok in name for tok in _CHICAGO) or any(tok in name for tok in _SCREENING):
        return KIND_TMY_SCREENING
    if "tmy" in name and ("madison" in name or "msn" in name):
        return KIND_TMY_MSN
    if "tmy" in name:
        return KIND_TMY_SCREENING
    return KIND_UNKNOWN


def _weather_dir(site: Path) -> Path:
    return Path(site) / "eplus" / "weather"


def resolve_amy_epw(site: Path, *, published: Path | None = None) -> Path | None:
    if published is not None and Path(published).is_file():
        if classify_epw(published) == KIND_AMY:
            return Path(published)
    weather = _weather_dir(site)
    if not weather.is_dir():
        return None
    cands = sorted(weather.glob("madison_amy*.epw")) or sorted(weather.glob("*amy*.epw"))
    return cands[0] if cands else None


def resolve_tmy_msn_epw(site: Path) -> Path | None:
    """Madison MSN TMY only — excludes Chicago / screening stand-ins."""
    weather = _weather_dir(site)
    if not weather.is_dir():
        return None
    hits: list[Path] = []
    for pat in ("*Madison*TMY*.epw", "*MSN*TMY*.epw", "*madison*tmy*.epw", "*msn*tmy*.epw"):
        hits.extend(weather.glob(pat))
    seen: set[str] = set()
    for p in sorted(hits):
        key = str(p.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if classify_epw(p) == KIND_TMY_MSN:
            return p
    return None


def weather_inventory(site: Path, *, published: Path | None = None) -> dict[str, Any]:
    amy = resolve_amy_epw(site, published=published)
    tmy = resolve_tmy_msn_epw(site)
    return {
        "amy": amy,
        "tmy": tmy,
        "amy_kind": classify_epw(amy) if amy else None,
        "tmy_kind": classify_epw(tmy) if tmy else None,
        "default_mode": "Both" if (amy and tmy) else "AMY",
        "tmy_missing_note": (
            None
            if tmy
            else (
                "No Madison MSN TMY3/TMYx under eplus/weather. "
                "AMY (Open-Meteo actual year) is the M&V file. "
                "Download MSN TMY to enable Both / typical-year. "
                "Chicago O'Hare screening EPW is not used."
            )
        ),
    }


def epws_for_mode(mode: str, inv: dict[str, Any]) -> list[tuple[str, Path]]:
    """Return (weather_kind, path) pairs for AMY / TMY / Both."""
    raw = (mode or "AMY").strip()
    amy = inv.get("amy")
    tmy = inv.get("tmy")
    if raw == "TMY":
        if tmy is None:
            return [(KIND_AMY, amy)] if amy else []
        return [(KIND_TMY_MSN, tmy)]
    if raw == "Both":
        out: list[tuple[str, Path]] = []
        if amy is not None:
            out.append((KIND_AMY, amy))
        if tmy is not None:
            out.append((KIND_TMY_MSN, tmy))
        return out
    return [(KIND_AMY, amy)] if amy else []
