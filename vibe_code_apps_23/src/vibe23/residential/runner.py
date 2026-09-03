"""Native EnergyPlus runner and CSV parser for residential day sims."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ..energyplus import inspect_energyplus_run, resolve_native_energyplus, sha256_file
from .constants import DT_HOURS, INTERVALS_PER_DAY
from .idf_patch import prepare_residential_idf
from .model import MODEL_IDF, equipment_provenance, find_denver_epw
from .thermostat import baseline_setpoints_f, c_to_f

_FACILITY_RE = re.compile(r"Electricity:Facility", re.IGNORECASE)
_ZONE_TEMP_RE = re.compile(r"Zone Mean Air Temperature", re.IGNORECASE)
_HVAC_RE = re.compile(r"Electricity:HVAC", re.IGNORECASE)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_eplus_csv(run_dir: Path | str) -> pd.DataFrame:
    """Parse eplusout.csv into facility_kw, zone_temp_f, optional hvac_kw."""

    root = Path(run_dir)
    csv_path = root / "eplusout.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"missing eplusout.csv in {root}")
    frame = pd.read_csv(csv_path)
    if frame.empty:
        raise ValueError("eplusout.csv has no data rows")
    cols = list(frame.columns)
    facility_col = next((c for c in cols if _FACILITY_RE.search(str(c))), None)
    zone_col = next((c for c in cols if _ZONE_TEMP_RE.search(str(c))), None)
    hvac_col = next((c for c in cols if _HVAC_RE.search(str(c))), None)
    if facility_col is None:
        raise ValueError("Electricity:Facility column not found")
    if zone_col is None:
        raise ValueError("Zone Mean Air Temperature column not found")

    facility_j = pd.to_numeric(frame[facility_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    facility_kw = facility_j / (DT_HOURS * 3_600_000.0)
    zone_c = pd.to_numeric(frame[zone_col], errors="coerce").to_numpy(dtype=float)
    zone_temp_f = np.array([c_to_f(v) if np.isfinite(v) else np.nan for v in zone_c], dtype=float)
    out = pd.DataFrame(
        {
            "timestamp": frame.iloc[:, 0].astype(str),
            "facility_kw": facility_kw,
            "zone_temp_f": zone_temp_f,
        }
    )
    if hvac_col is not None:
        hvac_j = pd.to_numeric(frame[hvac_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        out["hvac_kw"] = hvac_j / (DT_HOURS * 3_600_000.0)
    return out


def _resample_288(values: Sequence[float], n: int = INTERVALS_PER_DAY) -> list[float]:
    arr = np.asarray(list(values), dtype=float)
    if len(arr) == n:
        return arr.tolist()
    if len(arr) == 0:
        return [0.0] * n
    if len(arr) > n:
        return arr[:n].tolist()
    pad = np.full(n - len(arr), arr[-1], dtype=float)
    return np.concatenate([arr, pad]).tolist()


def run_residential_day(
    idf_text_or_path: str | Path,
    *,
    epw: Path | str | None = None,
    output_dir: Path | str,
    eplus_path: Path | str | None = None,
    month: int = 7,
    day: int = 15,
    heat_f: Sequence[float] | None = None,
    cool_f: Sequence[float] | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Run one weather-file day and return metrics with provenance hashes."""

    exe = resolve_native_energyplus(eplus_path)
    if exe is None:
        raise RuntimeError("native EnergyPlus executable not found")
    epw_path = find_denver_epw(epw)
    if epw_path is None:
        raise FileNotFoundError("Denver/Golden EPW not found")

    if isinstance(idf_text_or_path, Path) or (
        isinstance(idf_text_or_path, str) and "\n" not in idf_text_or_path and Path(idf_text_or_path).is_file()
    ):
        text = Path(idf_text_or_path).read_text(encoding="utf-8")
        source_idf = str(Path(idf_text_or_path).resolve())
    else:
        text = str(idf_text_or_path)
        source_idf = str(MODEL_IDF)

    heat, cool = baseline_setpoints_f()
    if heat_f is not None:
        heat = np.asarray(heat_f, dtype=float)
    if cool_f is not None:
        cool = np.asarray(cool_f, dtype=float)
    patched = prepare_residential_idf(text, month=month, day=day, heat_f=heat, cool_f=cool)

    out = Path(output_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    staged_idf = out / "in.idf"
    staged_idf.write_text(patched, encoding="utf-8")

    cmd = [str(exe), "-x", "-w", str(epw_path), "-d", str(out), "-r", str(staged_idf)]
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    wall_seconds = time.perf_counter() - started
    (out / "console.log").write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")

    version = None
    ver = subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=False)
    if ver.returncode == 0:
        version = (ver.stdout or ver.stderr or "").strip() or None

    inspection = inspect_energyplus_run(
        out,
        idf=staged_idf,
        epw=epw_path,
        energyplus_version=version,
        process_returncode=proc.returncode,
        require_zero_warnings=False,
    )
    fatal = int(inspection.get("fatal_count") or 0)
    severe = int(inspection.get("severe_count") or 0)
    csv_ok = bool((out / "eplusout.csv").is_file())
    soft_ok = proc.returncode == 0 and fatal == 0 and csv_ok

    facility_kw: list[float] = []
    zone_temp_f: list[float] = []
    peak_kw = 0.0
    total_kwh = 0.0
    if csv_ok:
        parsed = parse_eplus_csv(out)
        facility_kw = _resample_288(parsed["facility_kw"].tolist())
        zone_temp_f = _resample_288(parsed["zone_temp_f"].tolist())
        peak_kw = float(max(facility_kw)) if facility_kw else 0.0
        total_kwh = float(sum(v * DT_HOURS for v in facility_kw))

    return {
        "schema": "vibe23.residential_day_metrics.v1",
        "ok": soft_ok and severe == 0,
        "soft_ok": soft_ok,
        "process_returncode": proc.returncode,
        "fatal_count": fatal,
        "severe_count": severe,
        "warning_count": int(inspection.get("warning_count") or 0),
        "wall_seconds": float(wall_seconds),
        "facility_kw": facility_kw,
        "zone_temp_f": zone_temp_f,
        "peak_kw": peak_kw,
        "total_kwh": total_kwh,
        "month": int(month),
        "day": int(day),
        "idf_sha256": sha256_file(staged_idf),
        "epw_sha256": sha256_file(epw_path),
        "patched_idf_sha256": _sha256_text(patched),
        "source_idf": source_idf,
        "epw": str(epw_path),
        "output_dir": str(out.resolve()),
        "energyplus_version": version,
        "equipment": equipment_provenance(),
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "inspection": inspection,
    }
