"""Loader for the vibe19 WattLab dump (Export → "Build WattLab dump (zip)").

One entry point for everything vibe19 exports: MANIFEST.json, model seed,
inferred schedules, OAT-bin operating signatures, sensor stats / 24h diurnal
profiles, setpoint medians, mech-cooling bins + coverage, FDD findings +
per-rule timeseries, analytic CSVs, observed weather and utility bills. Also
produces the **gap report** — the explicit checklist of characteristics the
human must still provide (geometry, bills, rates, costs) before the digital
twin is trustworthy.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# filename → attribute (CSV tables)
_CSV_TABLES = {
    "operating_signatures.csv": "operating_signatures",
    "schedule_inference_table.csv": "schedule_inference_table",
    "sensor_stats_all.csv": "sensor_stats_all",
    "sensor_stats_fan_on.csv": "sensor_stats_fan_on",
    "sensor_stats_fan_off.csv": "sensor_stats_fan_off",
    "sensor_diurnal_24h.csv": "sensor_diurnal_24h",
    "setpoints.csv": "setpoints",
    "mech_cooling_oat_bins.csv": "mech_cooling_oat_bins",
    "mech_cooling_coverage.csv": "mech_cooling_coverage",
    "motor_hours.csv": "motor_hours",
    "motor_weekly.csv": "motor_weekly",
    "economizer_weather.csv": "economizer_weather",
    "fdd_summary.csv": "fdd_summary",
    "fdd_findings.csv": "fdd_findings",
    "weather_observed.csv": "weather_observed",
    "utility_bills.csv": "utility_bills",
    "rcx_preset_coverage.csv": "rcx_preset_coverage",
    "rcx_zone_comfort_ranking.csv": "rcx_zone_comfort_ranking",
    "role_map_gap_report.csv": "role_map_gap_report",
    "topology.csv": "topology",
    "data_model.csv": "data_model",
    "sensor_health_matrix.csv": "sensor_health_matrix",
    "sensor_fault_summary.csv": "sensor_fault_summary",
    "meter_monthly_electric.csv": "meter_monthly_electric",
    "meter_monthly_gas.csv": "meter_monthly_gas",
}

_JSON_DOCS = {
    "model_seed.json": "model_seed",
    "schedule_inference.json": "schedule_inference",
    "run_report.json": "run_report",
    "fault_settings.json": "fault_settings",
    "session_config.json": "session_config",
    "quick_savings.json": "quick_savings",
    "building_profile.json": "building_profile",
    "MANIFEST.json": "manifest",
}


@dataclass
class SeedBundle:
    """Parsed vibe19 dump. Missing artifacts stay as empty frames / ``{}``."""

    source: str = ""
    building_id: str = ""
    model_seed: dict[str, Any] = field(default_factory=dict)
    schedule_inference: dict[str, Any] = field(default_factory=dict)
    run_report: dict[str, Any] = field(default_factory=dict)
    fault_settings: dict[str, Any] = field(default_factory=dict)
    session_config: dict[str, Any] = field(default_factory=dict)
    quick_savings: dict[str, Any] = field(default_factory=dict)
    building_profile: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    files: dict[str, Path] = field(default_factory=dict)
    fdd_timeseries_dir: Path | None = None

    def table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    @property
    def operating_signatures(self) -> pd.DataFrame:
        return self.table("operating_signatures")

    @property
    def sensor_stats_all(self) -> pd.DataFrame:
        return self.table("sensor_stats_all")

    @property
    def fdd_summary(self) -> pd.DataFrame:
        return self.table("fdd_summary")

    @property
    def fdd_findings(self) -> pd.DataFrame:
        return self.table("fdd_findings")

    @property
    def sensor_diurnal_24h(self) -> pd.DataFrame:
        return self.table("sensor_diurnal_24h")

    @property
    def weather_observed(self) -> pd.DataFrame:
        return self.table("weather_observed")

    @property
    def utility_bills(self) -> pd.DataFrame:
        return self.table("utility_bills")

    @property
    def has_bills(self) -> bool:
        return not self.utility_bills.empty

    @property
    def has_observed_weather(self) -> bool:
        return not self.weather_observed.empty

    def summary(self) -> dict[str, Any]:
        seed = self.model_seed or {}
        return {
            "source": self.source,
            "building_id": self.building_id,
            "building_type": seed.get("building_type"),
            "city": seed.get("city"),
            "floor_area_ft2": seed.get("floor_area_ft2"),
            "data_window": seed.get("data_window") or (self.schedule_inference or {}).get("data_window"),
            "tables": {k: len(v) for k, v in self.tables.items()},
            "has_bills": self.has_bills,
            "has_observed_weather": self.has_observed_weather,
            "fault_rows": len(self.fdd_summary),
            "findings_rows": len(self.fdd_findings),
            "has_manifest": bool(self.manifest),
            "has_fdd_timeseries": bool(
                self.fdd_timeseries_dir and self.fdd_timeseries_dir.is_dir()
            ),
        }


def _load_dir(root: Path, bundle: SeedBundle) -> SeedBundle:
    for name, attr in _JSON_DOCS.items():
        p = root / name
        if p.is_file():
            try:
                setattr(bundle, attr, json.loads(p.read_text(encoding="utf-8")))
                bundle.files[name] = p
            except json.JSONDecodeError:
                pass
    for name, key in _CSV_TABLES.items():
        p = root / name
        if p.is_file():
            try:
                bundle.tables[key] = pd.read_csv(p)
                bundle.files[name] = p
            except Exception:
                pass
    seed = bundle.model_seed or {}
    bundle.building_id = str(
        seed.get("project_id")
        or seed.get("building_id")
        or (bundle.run_report or {}).get("building_id")
        or root.name
    )
    # Bills may live inside model_seed.json instead of a CSV
    if "utility_bills" not in bundle.tables:
        bills = seed.get("utility_bills")
        if isinstance(bills, list) and bills:
            bundle.tables["utility_bills"] = pd.DataFrame(bills)
    ts_dir = root / "fdd_timeseries"
    if ts_dir.is_dir():
        bundle.fdd_timeseries_dir = ts_dir
    return bundle


def load_bundle(path: str | Path, *, extract_dir: str | Path | None = None) -> SeedBundle:
    """Load a WattLab dump from a folder or zip.

    Zips are extracted to ``extract_dir`` (or a temp dir that outlives the
    returned bundle via ``bundle.files``). The dump root may be the zip root or
    a single top-level folder inside it.
    """
    p = Path(path)
    bundle = SeedBundle(source=str(p))
    if p.is_dir():
        return _load_dir(p, bundle)
    if not p.is_file():
        raise FileNotFoundError(f"WattLab dump not found: {p}")

    out = Path(extract_dir) if extract_dir else Path(tempfile.mkdtemp(prefix="wattlab_seed_"))
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p) as zf:
        zf.extractall(out)
    # Accept either flat zips or a single wrapping folder
    root = out
    entries = [e for e in out.iterdir() if not e.name.startswith("__MACOSX")]
    if len(entries) == 1 and entries[0].is_dir():
        root = entries[0]
    return _load_dir(root, bundle)


# ---------------------------------------------------------------------------
# Gap report — what the human still has to provide
# ---------------------------------------------------------------------------

_GAP_CHECKS: list[tuple[str, str, str]] = [
    # (field, severity, why)
    ("building_type", "required", "Prototype/archetype selection drives every default."),
    ("city", "required", "Weather file + climate-zone defaults."),
    ("floor_area_ft2", "required", "EUI normalization and autosizing sanity."),
    ("floors", "recommended", "Geometry massing (defaults to 1)."),
    ("wwr", "recommended", "Window-to-wall ratio for envelope loads."),
    ("hvac", "recommended", "Airside/plant topology (defaults from archetype)."),
    ("utility", "recommended", "Electric $/kWh + gas $/therm for ROI math."),
]


def gap_report(bundle: SeedBundle) -> list[dict[str, Any]]:
    """Checklist of missing characteristics for the human + agent to fill.

    Returns one row per gap: ``{"field", "severity", "why", "status"}`` —
    fields already present in the dump are included with ``status="ok"`` so the
    UI can render the full checklist with checkmarks.
    """
    seed = bundle.model_seed or {}
    profile = bundle.building_profile or {}
    rows: list[dict[str, Any]] = []
    for fieldname, severity, why in _GAP_CHECKS:
        val = seed.get(fieldname)
        if val in (None, "", {}, []):
            val = profile.get(fieldname)
        ok = val not in (None, "", {}, [])
        rows.append(
            {
                "field": fieldname,
                "severity": severity,
                "why": why,
                "status": "ok" if ok else "missing",
                "value": val if ok else None,
            }
        )
    rows.append(
        {
            "field": "utility_bills",
            "severity": "recommended",
            "why": "12 monthly kWh/therm rows unlock NMBE/CVRMSE calibration gates.",
            "status": "ok" if bundle.has_bills else "missing",
            "value": f"{len(bundle.utility_bills)} months" if bundle.has_bills else None,
        }
    )
    rows.append(
        {
            "field": "weather_observed",
            "severity": "recommended",
            "why": "Observed weather builds an AMY EPW for overlap-window calibration.",
            "status": "ok" if bundle.has_observed_weather else "missing",
            "value": f"{len(bundle.weather_observed)} rows" if bundle.has_observed_weather else None,
        }
    )
    rows.append(
        {
            "field": "measure_costs",
            "severity": "recommended",
            "why": "Installed costs per measure are needed for payback/ROI/NPV.",
            "status": "missing",
            "value": None,
        }
    )
    return rows
