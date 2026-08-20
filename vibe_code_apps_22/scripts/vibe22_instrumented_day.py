"""One instrumented Track B diagnostic day. Confirm RDD names before scoring coils."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.eplus_err import parse_eplus_err, scored_runtime_w2a_count
from eplus_gym.eplus_output_discovery import (
    WANTED_DIAGNOSTIC_VARIABLES,
    confirmed_diagnostic_variables,
    parse_rdd_variable_names,
)
from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.idf_diagnostics import inject_output_variables, strip_invalid_ideal_loads_and_district
from eplus_gym.idf_objects import field_by_comment, iter_objects
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_site_epw, sha256_file
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_gym.trackb_banks import HTG_TYPE
from eplus_gym.w2a_invalid_domain import classify_coil_timestep, count_active_invalid

ENABLE_RDD = """
OutputControl:Files,
  Yes,                     !- Output CSV
  Yes,                     !- Output MTR
  Yes,                     !- Output ESO
  Yes,                     !- Output EIO
  Yes,                     !- Output Tabular
  No,                      !- Output SQLite
  No,                      !- Output JSON
  Yes,                     !- Output AUDIT
  Yes,                     !- Output Space Sizing
  Yes,                     !- Output Zone Sizing
  Yes,                     !- Output System Sizing
  No,                      !- Output DXF
  Yes,                     !- Output BND
  Yes,                     !- Output RDD
  Yes;                     !- Output MDD

Output:VariableDictionary,
  IDF,                     !- Key Field
  Unsorted;                !- Sort Option
"""


def _enable_rdd(src: str) -> str:
    if "Output:VariableDictionary" in src:
        return src
    return src.rstrip() + "\n" + ENABLE_RDD + "\n"
RHO_KG_M3 = 1.204
TRACK_B = _APP / "models" / "eplus" / "research" / "a04_trackb_40fb33e8_NOT_CHAMPION.idf"
FIG = _APP / "docs" / "audits" / "figures" / "vibe22_final_physics_rl"


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _rated_air_kg_s(src: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for block in iter_objects(src, HTG_TYPE):
        name = field_by_comment(block, "Name") or ""
        raw = field_by_comment(block, "Rated Air Flow Rate") or "0"
        try:
            m3s = float(raw)
        except ValueError:
            m3s = 0.0
        out[name] = m3s * RHO_KG_M3
    return out


def _parse_csv_invalid(csv_path: Path, rated: dict[str, float]) -> list[dict]:
    if not csv_path.is_file():
        return []
    with csv_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        runtime_cols = [h for h in headers if "Heating Coil Runtime Fraction" in h]
        air_cols = [h for h in headers if "Heating Coil Air Mass Flow Rate" in h]
        rows_out: list[dict] = []
        for rec in reader:
            hour = rec.get("Date/Time") or rec.get("DateTime") or ""
            for rc in runtime_cols:
                coil = rc.split(":")[0].strip()
                ac = next((h for h in air_cols if h.startswith(coil + ":")), None)
                try:
                    rt = float(rec.get(rc) or 0)
                except ValueError:
                    rt = 0.0
                try:
                    air = float(rec.get(ac) or 0) if ac else 0.0
                except ValueError:
                    air = 0.0
                rated_air = 0.0
                for name, val in rated.items():
                    if name.split(" WAHP")[0] in coil or name in coil:
                        rated_air = val
                        break
                if coil + " Heating Coil" in rated:
                    rated_air = rated[coil + " Heating Coil"] if False else rated_air
                for name, val in rated.items():
                    if name in coil or coil in name:
                        rated_air = val
                        break
                rows_out.append(
                    classify_coil_timestep(
                        runtime_fraction=rt,
                        actual_air_kg_s=air,
                        rated_air_kg_s=rated_air,
                        coil=coil,
                        hour=hour,
                    )
                )
        return rows_out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="")
    p.add_argument("--day", default="2026-01-12")
    p.add_argument("--skip-instrumented", action="store_true")
    args = p.parse_args()
    site = require_site_root(args.site_root or None)
    epw = resolve_site_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned
    out = site / "reports" / "eplus_gym" / "final_physics" / f"trackb_instrumented_{args.day.replace('-', '')}"
    out.mkdir(parents=True, exist_ok=True)
    raw = TRACK_B.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    text = strip_invalid_ideal_loads_and_district(text, has_ideal_loads=False, has_district=False)
    text = _enable_rdd(text)
    cleaned = out / "trackb_cleaned.idf"
    cleaned.write_text(text, encoding="utf-8")
    staged_epw = stage_year_aware_epw(epw, out / f"staged_{epw.name}")
    epw_path = Path(staged_epw["staged_epw"])
    disc_idf = stage_idf_for_period(cleaned, out / "staged_discovery.idf", args.day, args.day)
    disc_dir = out / "discovery"
    r1 = run_energyplus_cli(idf=disc_idf, epw=epw_path, output=disc_dir, extra_args=["-r"], timeout_s=7200)
    rdd = disc_dir / "eplusout.rdd"
    rdd_text = rdd.read_text(encoding="utf-8", errors="replace") if rdd.is_file() else ""
    names = parse_rdd_variable_names(rdd_text)
    confirmed = confirmed_diagnostic_variables(rdd_text)
    _write(
        FIG / "rdd_discovery.json",
        {
            "schema": "vibe22.rdd_discovery.v1",
            "day": args.day,
            "idf_sha256": sha,
            "n_rdd_names": len(names),
            "confirmed": confirmed,
            "wanted_missing": [n for n in WANTED_DIAGNOSTIC_VARIABLES if n not in set(names)],
            "returncode": r1["returncode"],
            "rdd_bytes": rdd.stat().st_size if rdd.is_file() else 0,
        },
    )
    if args.skip_instrumented:
        print(json.dumps({"discovery_only": True, "confirmed": confirmed}))
        return 0 if r1["returncode"] == 0 else 2
    inst_src = inject_output_variables(text, confirmed + ["Zone Mean Air Temperature"], frequency="Timestep")
    inst_src = inject_output_variables(inst_src, ["Electricity:Facility"], frequency="Timestep")
    inst_idf = out / "trackb_instrumented.idf"
    inst_idf.write_text(inst_src, encoding="utf-8")
    staged_inst = stage_idf_for_period(inst_idf, out / "staged_instrumented.idf", args.day, args.day)
    inst_dir = out / "instrumented"
    r2 = run_energyplus_cli(idf=staged_inst, epw=epw_path, output=inst_dir, extra_args=["-r"], timeout_s=7200)
    err = inst_dir / "eplusout.err"
    gate = parse_eplus_err(err) if err.is_file() else {}
    rated = _rated_air_kg_s(text)
    classified = _parse_csv_invalid(inst_dir / "eplusout.csv", rated)
    active = count_active_invalid(classified)
    by_coil: dict[str, int] = {}
    for row in classified:
        if row.get("invalid_domain"):
            by_coil[str(row.get("coil"))] = by_coil.get(str(row.get("coil")), 0) + 1
    artifact = {
        "schema": "vibe22.instrumented_trackb_day.v1",
        "label": "DIAGNOSTIC FAILED MODEL",
        "day": args.day,
        "idf_sha256": sha,
        "discovery_returncode": r1["returncode"],
        "instrumented_returncode": r2["returncode"],
        "confirmed_variables": confirmed,
        "w2a_raw_err": {
            "scored_runtime": scored_runtime_w2a_count(gate) if gate else None,
            "warmup": (gate.get("w2a_low_airflow_by_phase") or {}).get("warmup"),
            "sizing": (gate.get("w2a_low_airflow_by_phase") or {}).get("sizing"),
            "total": (gate.get("w2a_low_airflow_by_phase") or {}).get("total") or gate.get("recurring", {}).get("w2a_low_airflow"),
        },
        "active_invalid_domain_count": active,
        "n_classified_rows": len(classified),
        "invalid_by_coil": by_coil,
        "severe_count": gate.get("severe_count"),
        "fatal_count": gate.get("fatal_count"),
        "utc": datetime.now(timezone.utc).isoformat(),
    }
    _write(out / "instrumented_day.json", artifact)
    _write(FIG / "instrumented_trackb_day.json", artifact)
    print(json.dumps({k: artifact[k] for k in artifact if k != "invalid_by_coil"}, indent=2))
    return 0 if r2["returncode"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
