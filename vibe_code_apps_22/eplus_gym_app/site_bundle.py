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
from typing import Any

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


@dataclass(frozen=True)
class NormalizedScorecard:
    """Unified GL14 / peak fields from IdealLoads or W2A scorecards."""

    peak_kw: float | None
    nmbe_pct: float | None
    cvrmse_pct: float | None
    gl14_pass: bool | None
    gates: dict[str, float]
    knobs: dict[str, Any]
    role: str | None
    source: Path | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelCatalogEntry:
    id: str
    label: str
    family: str
    idf_pin: str
    idf_path: Path | None
    scorecard_path: Path | None
    metrics: NormalizedScorecard | None
    champion: bool = False
    dial_id: str | None = None

    def dropdown_label(self) -> str:
        parts = [self.label]
        if self.metrics and self.metrics.peak_kw is not None:
            parts.append(f"{self.metrics.peak_kw:.0f} kW")
        if self.metrics and self.metrics.gl14_pass is True:
            parts.append("GL14 PASS")
        elif self.metrics and self.metrics.gl14_pass is False:
            parts.append("GL14 FAIL")
        elif self.family == "STRUCTURAL_LOAD_DIAGNOSTIC":
            parts.append("structural")
        return " · ".join(parts)


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
    model_catalog: tuple[ModelCatalogEntry, ...] = ()
    default_model_id: str = "A04"
    honesty: dict[str, str] = field(default_factory=dict)
    source_manifest: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def promote(self) -> bool:
        return False

    def get_model(self, model_id: str | None) -> ModelCatalogEntry | None:
        if not self.model_catalog:
            return None
        mid = model_id or self.default_model_id
        for m in self.model_catalog:
            if m.id == mid:
                return m
        for m in self.model_catalog:
            if m.champion:
                return m
        return self.model_catalog[0]


def _rel(site: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return p
    return site / p


def _resolve_scorecard_path(site: Path, rel: str | None) -> Path | None:
    """Repo ``models/eplus/...`` first, else site-relative."""
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return p if p.is_file() else None
    # Prefer app-root relative (scorecards live in git)
    app_cand = _APP / p
    if app_cand.is_file():
        return app_cand
    site_cand = site / p
    if site_cand.is_file():
        return site_cand
    return None


def normalize_scorecard(doc: dict[str, Any], *, source: Path | None = None) -> NormalizedScorecard:
    """Normalize IdealLoads nested gl14 or W2A flat scorecard fields."""
    peak = doc.get("jan26_peak_kw")
    if peak is None and isinstance(doc.get("monthly"), list):
        peaks = [
            float(r["peak_kw_obs"])
            for r in doc["monthly"]
            if isinstance(r, dict) and r.get("peak_kw_obs") is not None
        ]
        peak = max(peaks) if peaks else None

    nmbe = doc.get("nmbe_pct")
    cvrmse = doc.get("cvrmse_pct")
    gl14_pass: bool | None = None
    gates: dict[str, float] = {}

    if "gl14_pass" in doc:
        gl14_pass = bool(doc["gl14_pass"])
    nested = doc.get("gl14")
    if isinstance(nested, dict):
        if nmbe is None and nested.get("nmbe_pct") is not None:
            nmbe = nested["nmbe_pct"]
        if cvrmse is None and nested.get("cvrmse_pct") is not None:
            cvrmse = nested["cvrmse_pct"]
    status = doc.get("gl14_status")
    if gl14_pass is None and status is not None:
        gl14_pass = str(status).strip().lower() in {"pass", "passed", "ok", "success"}

    raw_gates = doc.get("gl14_gates") or {}
    if isinstance(raw_gates, dict):
        for k, v in raw_gates.items():
            try:
                gates[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    if not gates and isinstance(nested, dict):
        # IdealLoads often only has status; keep empty gates
        pass

    knobs = doc.get("knobs") if isinstance(doc.get("knobs"), dict) else {}

    def _f(x: Any) -> float | None:
        if x is None:
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    return NormalizedScorecard(
        peak_kw=_f(peak),
        nmbe_pct=_f(nmbe),
        cvrmse_pct=_f(cvrmse),
        gl14_pass=gl14_pass,
        gates=gates,
        knobs=dict(knobs),
        role=str(doc["role"]) if doc.get("role") else None,
        source=source,
        raw=doc,
    )


def load_normalized_scorecard(path: Path) -> NormalizedScorecard:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return normalize_scorecard(doc, source=path)


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
        "default_model_id": "A04",
        "idf_pin": "lakeside_w2a_a04_dual_champion.idf",
        "farm_parquet": "eplus/dsm_farm_paired/heating_dsm_eplus_paired_15min_v1.parquet",
        "honesty": {
            "bas": "BAS_INTERVAL_METER",
            "dial_ladder": "W2A_PHYSICAL_DSM",
            "farm": "STRUCTURAL_LOAD_DIAGNOSTIC",
        },
        "model_catalog": [],
        "dial_ladder": {
            "peak_day": "2026-01-26",
            "precomputed_closeness_csv": (
                "plots/analytics/eplus_gl14_vs_peak285/"
                "winter_shape_closeness_a04_ladder.csv"
            ),
            "models": [],
        },
    }


def _load_catalog(
    site: Path, doc: dict[str, Any], warnings: list[str]
) -> tuple[ModelCatalogEntry, ...]:
    rows = doc.get("model_catalog") or []
    out: list[ModelCatalogEntry] = []
    for raw in rows:
        mid = str(raw.get("id") or "")
        if not mid:
            continue
        idf_pin = str(raw.get("idf_pin") or "")
        idf_path: Path | None = None
        if idf_pin:
            try:
                cand = resolve_eplus_model(idf_pin)
                if cand.is_file():
                    idf_path = cand
                else:
                    warnings.append(f"catalog {mid}: idf missing ({idf_pin})")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"catalog {mid}: idf resolve failed ({exc})")

        sc_path = _resolve_scorecard_path(site, raw.get("scorecard"))
        metrics: NormalizedScorecard | None = None
        if raw.get("scorecard") and sc_path is None:
            warnings.append(f"catalog {mid}: scorecard missing ({raw.get('scorecard')})")
        elif sc_path is not None:
            try:
                metrics = load_normalized_scorecard(sc_path)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"catalog {mid}: scorecard parse failed ({exc})")

        out.append(
            ModelCatalogEntry(
                id=mid,
                label=str(raw.get("label") or mid),
                family=str(raw.get("family") or "UNKNOWN"),
                idf_pin=idf_pin,
                idf_path=idf_path,
                scorecard_path=sc_path,
                metrics=metrics,
                champion=bool(raw.get("champion")),
                dial_id=str(raw["dial_id"]) if raw.get("dial_id") else None,
            )
        )
    return tuple(out)


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

    catalog = _load_catalog(site, doc, warnings)
    default_model_id = str(doc.get("default_model_id") or "A04")
    if catalog and not any(m.id == default_model_id for m in catalog):
        champ = next((m for m in catalog if m.champion), catalog[0])
        default_model_id = champ.id
        warnings.append(f"default_model_id missing; using {default_model_id}")

    # Active IDF: prefer catalog default, else top-level idf_pin
    idf_path: Path | None = None
    default_entry = next((m for m in catalog if m.id == default_model_id), None)
    if default_entry and default_entry.idf_path is not None:
        idf_path = default_entry.idf_path
    else:
        idf_pin = doc.get("idf_pin")
        if idf_pin:
            try:
                cand = resolve_eplus_model(str(idf_pin))
                if cand.is_file():
                    idf_path = cand
                else:
                    warnings.append(f"idf_pin not found: {idf_pin}")
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

    honesty = {str(k): str(v) for k, v in (doc.get("honesty") or {}).items()}
    honesty.setdefault("bas", "BAS_INTERVAL_METER")
    honesty.setdefault("dial_ladder", "W2A_PHYSICAL_DSM")
    honesty.setdefault("farm", "STRUCTURAL_LOAD_DIAGNOSTIC")
    honesty.setdefault("massing", "PUBLISHED_IDF_GEOMETRY")

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
        model_catalog=catalog,
        default_model_id=default_model_id,
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


def catalog_gl14_table(bundle: SiteUiBundle) -> list[dict[str, Any]]:
    """Rows for Streamlit comparison table of catalog models with metrics."""
    rows: list[dict[str, Any]] = []
    for m in bundle.model_catalog:
        met = m.metrics
        rows.append(
            {
                "id": m.id,
                "label": m.label,
                "family": m.family,
                "idf": m.idf_pin,
                "peak_kw": met.peak_kw if met else None,
                "nmbe_pct": met.nmbe_pct if met else None,
                "cvrmse_pct": met.cvrmse_pct if met else None,
                "gl14": (
                    "PASS"
                    if met and met.gl14_pass is True
                    else ("FAIL" if met and met.gl14_pass is False else "—")
                ),
                "champion": m.champion,
            }
        )
    return rows
