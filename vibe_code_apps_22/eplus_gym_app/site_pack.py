"""Scan a zip/folder site pack and publish ``site_ui_bundle_v1``.

Agents (or a one-shot Streamlit drop) ingest vibe20-shaped artifacts:
``campus.json`` + bill CSVs, an IDF, an interval CSV, optional WattLab dump.
This is a scanner — not a WattLab clone.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from eplus_gym_app.campus_fuel import Campus
from eplus_gym_app.site_bundle import SCHEMA, _EXAMPLE

DSM_FARM_REL = "eplus/dsm_farm_w2a/heating_dsm_w2a_15min_v1.parquet"
IDEAL_FARM_REL = "eplus/dsm_farm_paired/heating_dsm_eplus_paired_15min_v1.parquet"


def _model_id_from_idf(path: Path) -> str:
    """Derive a short model id from an IDF filename (practice packs may use A04)."""
    low = path.stem.lower()
    for token in ("a04", "e20", "l22", "r02", "sc02"):
        if token in low:
            return token.upper()
    if "champion" in low:
        return "CHAMPION"
    clean = "".join(c if c.isalnum() else "_" for c in path.stem)
    return (clean[:40] or "CHAMPION").upper()


class SitePackError(ValueError):
    """Closed-gate pack / publish failure."""


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    status: str  # ok | missing | extra
    path: Path | None = None
    note: str = ""


@dataclass
class SitePackInventory:
    root: Path
    campus_json: Path | None = None
    idfs: list[Path] = field(default_factory=list)
    champion_idf: Path | None = None
    interval_csvs: list[Path] = field(default_factory=list)
    interval_csv: Path | None = None
    dump_manifest: Path | None = None
    data_model_csv: Path | None = None
    model_seed: Path | None = None
    scorecards: list[Path] = field(default_factory=list)
    epws: list[Path] = field(default_factory=list)
    existing_bundle: Path | None = None
    checklist: list[ReadinessItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def fuel_ready(self) -> bool:
        return self.campus_json is not None and any(
            i.key == "campus" and i.status == "ok" for i in self.checklist
        )

    @property
    def twin_ready(self) -> bool:
        return self.champion_idf is not None

    @property
    def actual_ready(self) -> bool:
        return self.interval_csv is not None


def _unwrap_root(path: Path) -> Path:
    if path.is_file():
        return path
    kids = [p for p in path.iterdir() if not p.name.startswith(".")]
    if len(kids) == 1 and kids[0].is_dir():
        return kids[0]
    return path


def _zip_member_parts(filename: str) -> tuple[str, ...]:
    normalized = filename.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    parts = tuple(part for part in member_path.parts if part not in ("", "."))
    if not parts:
        return ()
    if (
        member_path.is_absolute()
        or ".." in parts
        or any(part.endswith(":") for part in parts)
        or (len(parts) >= 2 and parts[0] in ("/", "//"))
        or normalized.startswith("//")
    ):
        raise SitePackError(f"Unsafe path in site pack zip: {filename!r}")
    return parts


def extract_pack(src: Path) -> Path:
    """Return an unwrapped folder root (extracts zip to a temp dir)."""
    src = Path(src)
    if not src.exists():
        raise SitePackError(f"site pack not found: {src}")
    if src.is_dir():
        return _unwrap_root(src)
    if src.suffix.lower() != ".zip":
        raise SitePackError(f"expected a folder or .zip, got {src}")
    dest = Path(tempfile.mkdtemp(prefix="vibe22_site_pack_")).resolve()
    with zipfile.ZipFile(src, "r") as zf:
        for member in zf.infolist():
            parts = _zip_member_parts(member.filename)
            if not parts:
                continue
            target = dest.joinpath(*parts).resolve()
            try:
                target.relative_to(dest)
            except ValueError as exc:
                raise SitePackError(
                    f"Unsafe path in site pack zip: {member.filename!r}"
                ) from exc
            normalized_name = member.filename.replace("\\", "/")
            if member.is_dir() or normalized_name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    return _unwrap_root(dest)


def _try_campus(path: Path) -> bool:
    try:
        Campus.from_json(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def _looks_interval_csv(path: Path) -> bool:
    name = path.name.lower()
    if any(
        tok in name
        for tok in (
            "demand_vs_web_weather",
            "demand_interval",
            "demand_hourly",
            "interval_kw",
        )
    ):
        return True
    if "utility_vs_interval" in name:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
    except OSError:
        return False
    if not head:
        return False
    cols = {c.strip().lower() for c in head[0].split(",")}
    has_ts = any("timestamp" in c or c == "hour_utc" for c in cols)
    has_kw = any(
        k in c for c in cols for k in ("kw_demand", "kw_avg", "electric_kw", "kw")
    )
    return has_ts and has_kw


A04_IDF_NAME = "lakeside_w2a_a04_dual_champion.idf"


def _pick_champion_idf(idfs: list[Path], *, site: Path | None = None) -> Path | None:
    """Prefer exact A04 dual champion; never 'first *champion*' or E20 when A04 exists."""
    if not idfs and site is None:
        return None
    pool = list(idfs)

    def _exact_a04(cands: list[Path]) -> Path | None:
        for p in cands:
            if p.name.lower() == A04_IDF_NAME.lower():
                return p
        return None

    hit = _exact_a04(pool)
    if hit is not None:
        return hit

    # Site-local search only (never invent A04 from the repo into a generic pack).
    if site is not None:
        for root in (Path(site), Path(site) / "eplus" / "models"):
            if not root.exists():
                continue
            direct = root / A04_IDF_NAME
            if direct.is_file():
                return direct
            if root.is_dir():
                for p in root.glob(A04_IDF_NAME):
                    if p.is_file():
                        return p

    # Lakeside practice fallback: repo models/eplus A04 only when pack already looks Lakeside.
    lakesideish = any("lakeside" in p.name.lower() or "a04" in p.name.lower() for p in pool)
    if lakesideish:
        app_root = Path(__file__).resolve().parents[1]
        repo_models = app_root / "models" / "eplus"
        if repo_models.is_dir():
            direct = repo_models / A04_IDF_NAME
            if direct.is_file():
                return direct

    for p in pool:
        if "a04" in p.name.lower():
            return p
    if pool:
        # Prefer *champion* only among generic names (no E20 token race vs A04 — A04 already handled).
        champs = [p for p in pool if "champion" in p.name.lower()]
        if champs:
            return sorted(champs, key=lambda p: p.name.lower())[0]
        return sorted(pool, key=lambda p: p.name.lower())[0]
    return None


def _pick_interval(cands: list[Path]) -> Path | None:
    if not cands:
        return None
    for p in cands:
        if p.name == "demand_vs_web_weather_hourly.csv":
            return p
    for p in cands:
        if p.name.startswith("demand_interval"):
            return p
    return cands[0]


def _pick_campus(root: Path) -> tuple[Path | None, list[Path]]:
    found = sorted(_iter_matches(root, "campus*.json"))
    utility = [p for p in found if p.name == "campus_utility.json" and _try_campus(p)]
    if utility:
        return utility[0], found
    ok = [p for p in found if _try_campus(p)]
    if ok:
        # Prefer utilities/campus.json over nested copies
        ok.sort(key=lambda p: (0 if p.parent.name == "utilities" else 1, len(p.parts)))
        return ok[0], found
    return (found[0] if found else None), found


_SCAN_REL = (
    "utilities",
    "reports",
    "eplus/models",
    "eplus/weather",
    "eplus/scorecards",
    "uploads",
    "packages",
    "plots",
)
_SKIP_DIR_NAMES = {
    "campaigns",
    "dsm_farm",
    "dsm_farm_paired",
    "dsm_farm_w2a",
    "dsm_native",
    "target",
    ".git",
    "__pycache__",
    "archive",
}


def _iter_matches(root: Path, pattern: str):
    """Search pack layout folders; never walk E+ campaign trees."""
    found: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        if not p.is_file():
            return
        if any(part in _SKIP_DIR_NAMES for part in p.parts):
            return
        key = str(p.resolve())
        if key in seen:
            return
        seen.add(key)
        found.append(p)

    structured = [root / rel for rel in _SCAN_REL if (root / rel).exists()]
    if structured:
        for p in root.glob(pattern):
            _add(p)
        for base in structured:
            if base.is_file():
                if base.match(pattern) or base.name.lower() == pattern.lower():
                    _add(base)
                continue
            for p in base.rglob(pattern):
                _add(p)
    else:
        for p in root.rglob(pattern):
            _add(p)
    return found


def inventory_site_pack(root: Path) -> SitePackInventory:
    root = _unwrap_root(Path(root))
    inv = SitePackInventory(root=root)
    campus, all_campus = _pick_campus(root)
    inv.campus_json = campus if campus and _try_campus(campus) else None

    inv.idfs = sorted(_iter_matches(root, "*.idf"))
    inv.champion_idf = _pick_champion_idf(inv.idfs, site=root)

    inv.interval_csvs = [p for p in _iter_matches(root, "*.csv") if _looks_interval_csv(p)]
    inv.interval_csv = _pick_interval(inv.interval_csvs)

    manifests = _iter_matches(root, "MANIFEST.json")
    inv.dump_manifest = manifests[0] if manifests else None
    dms = _iter_matches(root, "data_model.csv")
    inv.data_model_csv = dms[0] if dms else None
    seeds = _iter_matches(root, "model_seed.json")
    inv.model_seed = seeds[0] if seeds else None
    inv.scorecards = sorted(_iter_matches(root, "*scorecard*.json"))
    inv.epws = sorted(_iter_matches(root, "*.epw"))
    bundle = root / "reports" / "site_ui_bundle_v1.json"
    if bundle.is_file():
        inv.existing_bundle = bundle

    def _item(key: str, ok: bool, path: Path | None, missing_note: str, ok_note: str = "") -> None:
        inv.checklist.append(
            ReadinessItem(
                key=key,
                status="ok" if ok else "missing",
                path=path,
                note=ok_note if ok else missing_note,
            )
        )

    _item(
        "campus",
        inv.campus_json is not None,
        inv.campus_json,
        "campus.json + sibling bill CSVs required (vibe20 Campus)",
        "billing campus" if inv.campus_json and inv.campus_json.name == "campus_utility.json" else "campus ok",
    )
    _item(
        "idf",
        inv.champion_idf is not None,
        inv.champion_idf,
        "at least one .idf required (prefer *champion*)",
        inv.champion_idf.name if inv.champion_idf else "",
    )
    _item(
        "interval",
        inv.interval_csv is not None,
        inv.interval_csv,
        "interval / demand CSV required for Actual traces",
        inv.interval_csv.name if inv.interval_csv else "",
    )
    _item(
        "data_model",
        inv.dump_manifest is not None or inv.data_model_csv is not None,
        inv.data_model_csv or inv.dump_manifest,
        "recommended: WattLab dump MANIFEST.json + data_model.csv",
        "dump present",
    )
    _item(
        "epw",
        bool(inv.epws),
        inv.epws[0] if inv.epws else None,
        "recommended: AMY/TMY .epw for live DSM",
        inv.epws[0].name if inv.epws else "",
    )
    if all_campus and len(all_campus) > 1:
        inv.checklist.append(
            ReadinessItem(
                key="campus_extra",
                status="extra",
                path=all_campus[0],
                note=f"{len(all_campus)} campus*.json files; billing preferred",
            )
        )
    return inv


def _rel_to(site: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(site.resolve()).as_posix()
    except ValueError:
        return path.name


def _copy_file(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def _copy_campus_with_bills(campus: Path, dest_util: Path) -> Path:
    dest_campus = _copy_file(campus, dest_util / campus.name)
    try:
        doc = json.loads(campus.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dest_campus
    for meter in doc.get("meters") or []:
        fname = str(meter.get("file") or "")
        if not fname:
            continue
        src_bill = campus.parent / fname
        if src_bill.is_file():
            _copy_file(src_bill, dest_util / Path(fname).name)
    for extra in campus.parent.glob("*.csv"):
        _copy_file(extra, dest_util / extra.name)
    return dest_campus


def _load_example() -> dict[str, Any]:
    if _EXAMPLE.is_file():
        return json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    return {"schema_version": SCHEMA, "model_catalog": [], "dial_ladder": {"models": []}}


def publish_site_ui_bundle(
    site: Path,
    inventory: SitePackInventory | None = None,
    **overrides: Any,
) -> Path:
    """Write ``{site}/reports/site_ui_bundle_v1.json`` from inventory + example catalog."""
    site = Path(site)
    inv = inventory or inventory_site_pack(site)
    if inv.campus_json is None or not inv.fuel_ready:
        raise SitePackError(
            "campus.json + sibling bill CSVs required to publish site_ui_bundle_v1"
        )

    dest_campus = inv.campus_json
    if dest_campus.parent != site / "utilities":
        dest_campus = site / "utilities" / dest_campus.name
    dest_interval = inv.interval_csv
    if dest_interval is not None and not str(dest_interval).startswith(str(site)):
        dest_interval = site / "reports" / dest_interval.name

    doc = _load_example()
    existing = site / "reports" / "site_ui_bundle_v1.json"
    if existing.is_file():
        try:
            prior = json.loads(existing.read_text(encoding="utf-8"))
            if isinstance(prior, dict):
                # Keep agent-published dial_ladder / catalog when already on site
                for key in ("model_catalog", "dial_ladder", "honesty"):
                    if prior.get(key):
                        doc[key] = prior[key]
        except (OSError, json.JSONDecodeError):
            pass

    idf_pin = inv.champion_idf.name if inv.champion_idf is not None else ""
    model_id = _model_id_from_idf(inv.champion_idf) if inv.champion_idf else "CHAMPION"
    # Prefer inventory IDF. Only adopt a catalog champion when its idf_pin matches
    # (keeps practice packs on A04; avoids lakeside example overriding generic IDFs).
    for raw in doc.get("model_catalog") or []:
        if not (isinstance(raw, dict) and raw.get("champion") and raw.get("id")):
            continue
        cat_pin = str(raw.get("idf_pin") or "")
        if inv.champion_idf is not None and cat_pin and cat_pin != inv.champion_idf.name:
            continue
        model_id = str(raw["id"])
        if cat_pin:
            idf_pin = cat_pin
        break
    # Hard-prefer catalog A04 when present and pin matches A04 file.
    for raw in doc.get("model_catalog") or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id") or "").upper() != "A04":
            continue
        cat_pin = str(raw.get("idf_pin") or A04_IDF_NAME)
        if inv.champion_idf is not None and inv.champion_idf.name.lower() == A04_IDF_NAME.lower():
            model_id = "A04"
            idf_pin = inv.champion_idf.name
            break
        if cat_pin.lower() == A04_IDF_NAME.lower() and inv.champion_idf is not None:
            if "a04" in inv.champion_idf.name.lower():
                model_id = "A04"
                idf_pin = inv.champion_idf.name
                break
    if inv.champion_idf is not None and (
        not any(
            isinstance(r, dict)
            and r.get("champion")
            and str(r.get("idf_pin") or "") == inv.champion_idf.name
            for r in (doc.get("model_catalog") or [])
        )
    ):
        # Generic / non-example pack: publish a one-row catalog for this IDF.
        model_id = _model_id_from_idf(inv.champion_idf)
        idf_pin = inv.champion_idf.name
        doc["model_catalog"] = [
            {
                "id": model_id,
                "label": f"{model_id} champion",
                "family": "W2A_PHYSICAL_DSM",
                "idf_pin": idf_pin,
                "champion": True,
                "dial_id": model_id,
            }
        ]
        doc["dial_ladder"] = {
            "peak_day": (doc.get("dial_ladder") or {}).get("peak_day") or "2026-01-26",
            "models": [],
        }
    if not idf_pin and inv.champion_idf is not None:
        idf_pin = inv.champion_idf.name

    # Lakeside / A04 practice pack contract: never publish E20 as DSM champion when A04 exists.
    has_a04_file = inv.champion_idf is not None and (
        inv.champion_idf.name.lower() == A04_IDF_NAME.lower()
        or "a04" in inv.champion_idf.name.lower()
    )
    has_e20_token = any("e20" in p.name.lower() for p in inv.idfs)
    has_a04_anywhere = has_a04_file or any(
        p.name.lower() == A04_IDF_NAME.lower() or "a04" in p.name.lower() for p in inv.idfs
    )
    if has_a04_anywhere:
        if inv.champion_idf is None or not has_a04_file:
            raise SitePackError(
                f"A04 champion required ({A04_IDF_NAME}); refusing to publish non-A04 DSM champion"
            )
        model_id = "A04"
        idf_pin = inv.champion_idf.name
        # Ensure catalog row points at A04
        catalog = list(doc.get("model_catalog") or [])
        updated = False
        for raw in catalog:
            if isinstance(raw, dict) and str(raw.get("id") or "").upper() == "A04":
                raw["champion"] = True
                raw["idf_pin"] = idf_pin
                updated = True
            elif isinstance(raw, dict) and raw.get("champion"):
                raw["champion"] = False
        if not updated:
            catalog = [
                {
                    "id": "A04",
                    "label": "A04 dual champion",
                    "family": "W2A_PHYSICAL_DSM",
                    "idf_pin": idf_pin,
                    "champion": True,
                    "dial_id": "A04",
                }
            ]
        doc["model_catalog"] = catalog
    elif has_e20_token and not has_a04_anywhere and any(
        "lakeside" in p.name.lower() for p in inv.idfs
    ):
        raise SitePackError(
            f"Lakeside pack missing {A04_IDF_NAME}; refusing E20 fallback as DSM champion"
        )

    campus_rel = _rel_to(site, dest_campus) if dest_campus.is_file() else f"utilities/{dest_campus.name}"
    if dest_interval is not None and dest_interval.is_file():
        interval_rel = _rel_to(site, dest_interval)
    elif inv.interval_csv is not None:
        interval_rel = f"reports/{inv.interval_csv.name}"
    else:
        interval_rel = "reports/demand_vs_web_weather_hourly.csv"

    epw_rel = None
    if inv.epws:
        epw = inv.epws[0]
        dest_epw = epw if str(epw).startswith(str(site)) else site / "eplus" / "weather" / epw.name
        epw_rel = _rel_to(site, dest_epw) if dest_epw.is_file() else f"eplus/weather/{epw.name}"

    warnings = [
        i.note for i in inv.checklist if i.status == "missing" and i.key in {"data_model", "epw"}
    ]
    doc.update(
        {
            "schema_version": SCHEMA,
            "campus_json": campus_rel.replace("\\", "/"),
            "bas_demand_oat_csv": interval_rel.replace("\\", "/"),
            "default_model_id": model_id,
            "current_model_id": model_id,
            "dsm_champion": model_id,
            "idf_pin": idf_pin,
            "farm_parquet": IDEAL_FARM_REL,
            "dsm_farm_parquet": DSM_FARM_REL,
            "warnings": warnings,
        }
    )
    if epw_rel:
        doc["epw"] = epw_rel.replace("\\", "/")
    doc.update(overrides)

    # Post-publish A04 contract when A04 pack
    if has_a04_anywhere:
        if doc.get("current_model_id") != "A04" or doc.get("dsm_champion") != "A04":
            doc["current_model_id"] = "A04"
            doc["dsm_champion"] = "A04"
            doc["default_model_id"] = "A04"
        if inv.champion_idf is not None:
            doc["idf_pin"] = inv.champion_idf.name
            try:
                import hashlib

                h = hashlib.sha256()
                with inv.champion_idf.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        h.update(chunk)
                doc["idf_sha256"] = h.hexdigest()
            except OSError:
                pass
        if doc.get("dsm_champion") != "A04" or doc.get("idf_pin") != (
            inv.champion_idf.name if inv.champion_idf else doc.get("idf_pin")
        ):
            raise SitePackError(
                "publish assert failed: dsm_champion/current_model_id must be A04 "
                f"with idf_pin={A04_IDF_NAME}"
            )

    out = site / "reports" / "site_ui_bundle_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import os

    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


def ingest_site_pack(src: Path, dest_site: Path) -> SitePackInventory:
    """Extract/copy pack artifacts into site layout and publish the bundle."""
    dest_site = Path(dest_site)
    dest_site.mkdir(parents=True, exist_ok=True)
    root = extract_pack(Path(src))
    inv = inventory_site_pack(root)

    dest_util = dest_site / "utilities"
    dest_models = dest_site / "eplus" / "models"
    dest_reports = dest_site / "reports"
    dest_weather = dest_site / "eplus" / "weather"
    dest_dump = dest_site / "uploads" / "dump"
    dest_scores = dest_site / "eplus" / "scorecards"

    if inv.campus_json is not None:
        _copy_campus_with_bills(inv.campus_json, dest_util)
        # Also keep interval-integrated campus.json if present
        for extra in root.rglob("campus*.json"):
            if extra.resolve() == inv.campus_json.resolve():
                continue
            _copy_campus_with_bills(extra, dest_util)

    for idf in inv.idfs:
        _copy_file(idf, dest_models / idf.name)

    if inv.interval_csv is not None:
        name = inv.interval_csv.name
        if name == "demand_vs_web_weather_hourly.csv" or "demand" in name.lower():
            _copy_file(inv.interval_csv, dest_reports / name)
        else:
            _copy_file(inv.interval_csv, dest_util / name)

    if inv.dump_manifest is not None:
        _copy_file(inv.dump_manifest, dest_dump / "MANIFEST.json")
    if inv.data_model_csv is not None:
        _copy_file(inv.data_model_csv, dest_dump / "data_model.csv")
    if inv.model_seed is not None:
        _copy_file(inv.model_seed, dest_dump / "model_seed.json")
    for sc in inv.scorecards:
        _copy_file(sc, dest_scores / sc.name)
    for epw in inv.epws:
        _copy_file(epw, dest_weather / epw.name)

    staged = inventory_site_pack(dest_site)
    publish_site_ui_bundle(dest_site, staged)
    return inventory_site_pack(dest_site)
