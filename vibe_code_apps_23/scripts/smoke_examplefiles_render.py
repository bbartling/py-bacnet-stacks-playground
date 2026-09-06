"""Smoke a few EnergyPlus ExampleFiles + weather variants against the Render worker."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from vibe23.envfile import load_energyplus_env
from vibe23.energyplus_worker import ensure_worker_awake, run_day_via_worker

EPLUS_ROOT = Path(r"C:\EnergyPlusV26-1-0")
EXAMPLES = EPLUS_ROOT / "ExampleFiles"
WEATHER = EPLUS_ROOT / "WeatherData"

CASES = [
    ("1ZoneUncontrolled.idf", "USA_CO_Golden-NREL.724666_TMY3.epw"),
    ("1ZoneUncontrolled.idf", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"),
    ("1ZoneEvapCooler.idf", "USA_FL_Tampa.Intl.AP.722110_TMY3.epw"),
    ("1ZoneUncontrolledUTF8.idf", "USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw"),
]


def main() -> int:
    load_energyplus_env(override=True)
    os.environ["EPLUS_BACKEND"] = "worker"
    wake = ensure_worker_awake()
    print("wake", json.dumps({k: wake[k] for k in ("ok", "awake", "woke_from_sleep", "wall_seconds")}, indent=2))
    results: list[dict] = []
    for idf_name, epw_name in CASES:
        idf = EXAMPLES / idf_name
        epw = WEATHER / epw_name
        if not idf.is_file() or not epw.is_file():
            results.append({"idf": idf_name, "epw": epw_name, "ok": False, "error": "missing local file"})
            continue
        out = Path(tempfile.mkdtemp(prefix=f"ex_{idf.stem}_"))
        try:
            meta = run_day_via_worker(idf_path=idf, epw_path=epw, output_dir=out, timeout_seconds=960.0)
            csv_ok = (out / "eplusout.csv").is_file()
            status = meta.get("status")
            ok = (
                status == "succeeded"
                and csv_ok
                and int(meta.get("fatal_count") or 0) == 0
                and int(meta.get("severe_count") or 0) == 0
            )
            row = {
                "idf": idf_name,
                "epw": epw_name,
                "ok": ok,
                "status": status,
                "job_id": meta.get("worker_job_id") or meta.get("job_id"),
                "fatal": meta.get("fatal_count"),
                "severe": meta.get("severe_count"),
                "wall_s": meta.get("worker_wall_seconds"),
                "csv": csv_ok,
            }
        except Exception as exc:  # noqa: BLE001
            row = {"idf": idf_name, "epw": epw_name, "ok": False, "error": str(exc)[:300]}
        print(json.dumps(row))
        results.append(row)
    passed = sum(1 for r in results if r.get("ok"))
    print(f"SUMMARY {passed}/{len(results)} ok")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
