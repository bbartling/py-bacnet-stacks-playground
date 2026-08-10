"""vibe20-style site UI data model for the E+ gym Streamlit app.

Streamlit charts must bind to ``SiteUiBundle`` layers — never hard-code
campaign folders or machine paths in widgets.

Mirrors vibe20 ``Campus.from_json`` + DATA_CONTRACT publish spirit:
paths in the JSON are relative to ``LAKESIDE_SITE_ROOT``.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from lakeside.paths import resolve_eplus_model, site_root  # noqa: E402

SCHEMA = "site_ui_bundle_v1"
_EXAMPLE = _APP / "contracts" / "site_ui_bundle_v1.lakeside.example.json"


@dataclass(frozen=True)
class CampusRef:
    campus_id: str
    label: str
    lat: float | None
    lon: float | None
    site_ref: str | None
    source: Path
    floor_area_ft2: float | None = None


@dataclass(frozen=True)
class DialModelPin:
    id: str
    label: str
    honesty: str
    sim_dir: Path | None = None
    champion: bool = False


@dataclass(frozen=True)
class DialLadder:
    peak_day: str
    models: tuple[DialModelPin, ...]
    precomputed_closeness_csv: Path | None = None
    utility_peak_kw: float = 284.8


@dataclass
class SiteUiBundle:
    """Resolved site UI layers (all paths absolute after load)."""

    schema_version: str
    site: Path
    campus: CampusRef
    bas_demand_oat_csv: Path
    farm_parquet: Path | None
    idf_path: Path | None
    dial_ladder: DialLadder
    honesty: dict[str, str] = field(default_factory=dict)
    source_manifest: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def promote(self) -> bool:
        return False


def _rel(site: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return p
    return site / p


def _load_campus(path: Path) -> CampusRef:
    doc = json.loads(path.read_text(encoding="utf-8"))
    buildings = doc.get("buildings") or []
    area = None
    if buildings:
        try:
            area = float(buildings[0].get("floor_area_ft2"))
        except (TypeError, ValueError):
            area = None
    lat = doc.get("lat", doc.get("latitude"))
    lon = doc.get("lon", doc.get("longitude"))
    return CampusRef(
        campus_id=str(doc.get("campus_id") or path.stem),
        label=str(doc.get("label") or doc.get("campus_id") or path.stem),
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        site_ref=(
            str(doc["siteRef"])
            if doc.get("siteRef")
            else (str(doc["site_ref"]) if doc.get("site_ref") else None)
        ),
        source=path,
        floor_area_ft2=area,
    )


def _default_doc() -> dict[str, Any]:
    if _EXAMPLE.is_file():
        return json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    return {
        "schema_version": SCHEMA,
        "campus_json": "utilities/campus.json",
        "bas_demand_oat_csv": "reports/demand_vs_web_weather_hourly.csv",
        "utility_peak_kw": 284.8,
        "idf_pin": "lakeside_w2a_a04_dual_champion.idf",
        "farm_parquet": "eplus/dsm_farm_paired/heating_dsm_eplus_paired_15min_v1.parquet",
        "honesty": {
            "bas": "BAS_INTERVAL_METER",
            "dial_ladder": "W2A_PHYSICAL_DSM",
            "farm": "STRUCTURAL_LOAD_DIAGNOSTIC",
        },
        "dial_ladder": {
            "peak_day": "2026-01-26",
            "precomputed_closeness_csv": (
                "plots/analytics/eplus_gl14_vs_peak285/"
                "winter_shape_closeness_a04_ladder.csv"
            ),
            "models": [],
        },
    }


def load_site_ui_bundle(site: Path | None = None) -> SiteUiBundle:
    """Load site UI bundle; prefer ``{site}/reports/site_ui_bundle_v1.json``."""
    site = Path(site or site_root())
    warnings: list[str] = []
    manifest = site / "reports" / "site_ui_bundle_v1.json"
    source: Path | None = None
    if manifest.is_file():
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        source = manifest
    else:
        doc = _default_doc()
        warnings.append(
            f"missing {manifest.name}; using repo example defaults under contracts/"
        )

    schema = str(doc.get("schema_version") or SCHEMA)
    if schema != SCHEMA:
        warnings.append(f"unexpected schema_version={schema!r}; expected {SCHEMA}")

    campus_path = _rel(site, str(doc.get("campus_json") or "utilities/campus.json"))
    if campus_path is None or not campus_path.is_file():
        raise FileNotFoundError(
            f"campus.json not found at {campus_path} — vibe20 Campus contract required"
        )
    campus = _load_campus(campus_path)

    bas = _rel(site, str(doc.get("bas_demand_oat_csv") or ""))
    if bas is None or not bas.is_file():
        raise FileNotFoundError(f"bas_demand_oat_csv missing: {bas}")

    farm = _rel(site, doc.get("farm_parquet"))
    if farm is not None and not farm.is_file():
        warnings.append(f"farm_parquet missing: {farm}")
        farm = None

    idf_pin = doc.get("idf_pin")
    idf_path: Path | None = None
    if idf_pin:
        try:
            idf_path = resolve_eplus_model(str(idf_pin))
            if not idf_path.is_file():
                warnings.append(f"idf_pin not found: {idf_pin}")
                idf_path = None
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"idf_pin resolve failed: {exc}")

    dl = doc.get("dial_ladder") or {}
    models: list[DialModelPin] = []
    for m in dl.get("models") or []:
        sim = _rel(site, m.get("sim_dir"))
        if sim is not None and not sim.is_dir():
            warnings.append(f"dial model {m.get('id')}: sim_dir missing ({sim})")
            sim = None
        models.append(
            DialModelPin(
                id=str(m.get("id")),
                label=str(m.get("label") or m.get("id")),
                honesty=str(m.get("honesty") or "W2A_PHYSICAL_DSM"),
                sim_dir=sim,
                champion=bool(m.get("champion")),
            )
        )

    closeness = _rel(site, dl.get("precomputed_closeness_csv"))
    if closeness is not None and not closeness.is_file():
        warnings.append(f"precomputed_closeness_csv missing: {closeness}")
        closeness = None

    utility_peak = float(doc.get("utility_peak_kw") or dl.get("utility_peak_kw") or 284.8)
    peak_day = str(dl.get("peak_day") or "2026-01-26")

    honesty = {
        str(k): str(v) for k, v in (doc.get("honesty") or {}).items()
    }
    honesty.setdefault("bas", "BAS_INTERVAL_METER")
    honesty.setdefault("dial_ladder", "W2A_PHYSICAL_DSM")
    honesty.setdefault("farm", "STRUCTURAL_LOAD_DIAGNOSTIC")

    return SiteUiBundle(
        schema_version=schema,
        site=site,
        campus=campus,
        bas_demand_oat_csv=bas,
        farm_parquet=farm,
        idf_path=idf_path,
        dial_ladder=DialLadder(
            peak_day=peak_day,
            models=tuple(models),
            precomputed_closeness_csv=closeness,
            utility_peak_kw=utility_peak,
        ),
        honesty=honesty,
        source_manifest=source,
        warnings=warnings,
    )


def write_site_ui_bundle_example(dest: Path | None = None) -> Path:
    """Helper for agents: copy example manifest onto a site reports/ folder."""
    dest = Path(dest or (site_root() / "reports" / "site_ui_bundle_v1.json"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
