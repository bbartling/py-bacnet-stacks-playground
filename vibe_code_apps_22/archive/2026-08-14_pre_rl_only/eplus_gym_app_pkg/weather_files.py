"""Resolve AMY vs site TMY EPWs. Never auto-pick Chicago screening as TMY."""
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
        return KIND_TMY_MSN
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
    try:
        from lakeside.paths import site_slug

        slug = site_slug(site)
    except Exception:  # noqa: BLE001
        slug = Path(site).name.lower()
    cands = [p for p in weather.glob(f"{slug}_amy*.epw") if p.is_file()]
    if not cands:
        cands = [p for p in weather.glob("madison_amy*.epw") if p.is_file()]
    if not cands:
        cands = [p for p in weather.glob("*amy*.epw") if p.is_file()]
    if not cands:
        return None
    cands.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return cands[0]


def resolve_tmy_msn_epw(site: Path) -> Path | None:
    """Prefer Madison MSN TMY when present; else any non-Chicago TMY."""
    weather = _weather_dir(site)
    if not weather.is_dir():
        return None
    hits: list[Path] = []
    for pat in (
        "*Madison*TMY*.epw",
        "*MSN*TMY*.epw",
        "*madison*tmy*.epw",
        "*msn*tmy*.epw",
        "*TMY*.epw",
        "*tmy*.epw",
    ):
        hits.extend(weather.glob(pat))
    seen: set[str] = set()
    preferred: Path | None = None
    for p in sorted(hits):
        key = str(p.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        kind = classify_epw(p)
        if kind == KIND_TMY_SCREENING:
            continue
        if kind == KIND_TMY_MSN:
            name = p.name.lower()
            if "madison" in name or "msn" in name:
                return p
            if preferred is None:
                preferred = p
    return preferred


def weather_inventory(site: Path, *, published: Path | None = None) -> dict[str, Any]:
    amy = resolve_amy_epw(site, published=published)
    tmy = resolve_tmy_msn_epw(site)
    stale_bundle = False
    stale_note = None
    meta_path = _weather_dir(site) / "amy_meta.json"
    if meta_path.is_file():
        try:
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_epw = meta.get("epw")
            if meta_epw and published is not None and Path(published).is_file():
                try:
                    stale_bundle = Path(meta_epw).resolve() != Path(published).resolve()
                except OSError:
                    stale_bundle = Path(meta_epw).name != Path(published).name
                if stale_bundle:
                    stale_note = (
                        f"Published bundle EPW ({Path(published).name}) differs from "
                        f"amy_meta current ({Path(meta_epw).name}). Republish AMY / site pack."
                    )
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return {
        "amy": amy,
        "tmy": tmy,
        "amy_kind": classify_epw(amy) if amy else None,
        "tmy_kind": classify_epw(tmy) if tmy else None,
        "default_mode": "AMY",
        "stale_bundle_epw": stale_bundle,
        "stale_bundle_note": stale_note,
        "tmy_missing_note": (
            None
            if tmy
            else (
                "No site TMY under eplus/weather. "
                "AMY (Open-Meteo actual year) is the M&V file. "
                "Download a local TMY to enable Both / typical-year. "
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
