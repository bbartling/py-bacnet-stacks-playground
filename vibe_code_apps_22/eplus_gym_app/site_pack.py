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
CHAMPION_MODEL_ID = "A04"
A04_IDF = "lakeside_w2a_a04_dual_champion.idf"


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


def _pick_champion_idf(idfs: list[Path]) -> Path | None:
    if not idfs:
        return None
    for p in idfs:
        if "a04" in p.name.lower():
            return p
    for p in idfs:
        if "champion" in p.name.lower():
            return p
    return sorted(idfs, key=lambda p: p.name.lower())[0]


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
    found = sorted(root.rglob("campus*.json"))
    utility = [p for p in found if p.name == "campus_utility.json" and _try_campus(p)]
    if utility:
        return utility[0], found
    ok = [p for p in found if _try_campus(p)]
    if ok:
        # Prefer utilities/campus.json over nested copies
        ok.sort(key=lambda p: (0 if p.parent.name == "utilities" else 1, len(p.parts)))
        return ok[0], found
    return (found[0] if found else None), found


def inventory_site_pack(root: Path) -> SitePackInventory:
    root = _unwrap_root(Path(root))
    inv = SitePackInventory(root=root)
    campus, all_campus = _pick_campus(root)
    inv.campus_json = campus if campus and _try_campus(campus) else None

    inv.idfs = sorted(root.rglob("*.idf"))
    inv.champion_idf = _pick_champion_idf(inv.idfs)

    inv.interval_csvs = [p for p in root.rglob("*.csv") if _looks_interval_csv(p)]
    inv.interval_csv = _pick_interval(inv.interval_csvs)

    for p in root.rglob("MANIFEST.json"):
        inv.dump_manifest = p
        break
    for p in root.rglob("data_model.csv"):
        inv.data_model_csv = p
        break
    for p in root.rglob("model_seed.json"):
        inv.model_seed = p
        break
    inv.scorecards = sorted(root.rglob("*scorecard*.json"))
    inv.epws = sorted(root.rglob("*.epw"))
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
        "at least one .idf required (prefer A04 champion)",
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

    idf_pin = A04_IDF
    if inv.champion_idf is not None:
        idf_pin = inv.champion_idf.name

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
            "default_model_id": CHAMPION_MODEL_ID,
            "current_model_id": CHAMPION_MODEL_ID,
            "dsm_champion": CHAMPION_MODEL_ID,
            "idf_pin": idf_pin,
            "farm_parquet": IDEAL_FARM_REL,
            "dsm_farm_parquet": DSM_FARM_REL,
            "warnings": warnings,
        }
    )
    if epw_rel:
        doc["epw"] = epw_rel.replace("\\", "/")
    doc.update(overrides)

    out = site / "reports" / "site_ui_bundle_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
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
