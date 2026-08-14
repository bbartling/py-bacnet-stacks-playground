#!/usr/bin/env python3
"""Jan 26 2026 live baseline READY gate (Phase 0.5)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.simulate import run_rule_episode, trajectory_frame, validate_live_trajectory_calendar
from eplus_gym_app.dsm_console import stage_idf_for_period
from eplus_gym_app.dsm_preflight import sha256_file
from eplus_gym_app.site_bundle import load_site_ui_bundle
from eplus_native.idf_stage import disable_sizing_periods


def _epw_oat_c_for_day(epw: Path, day: str) -> list[float]:
    """Parse EPW dry-bulb °C for calendar day (hourly → expand to 15-min)."""
    y, m, d = [int(x) for x in day.split("-")]
    hours: list[float] = []
    for line in Path(epw).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            yy, mm, dd, hh = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            continue
        if yy == y and mm == m and dd == d:
            hours.append(float(parts[6]))
    # EPW hours often 1..24; take 24 values
    if len(hours) < 24:
        raise ValueError(f"EPW missing {day}: got {len(hours)} hours")
    hours = hours[:24]
    out: list[float] = []
    for h in hours:
        out.extend([h, h, h, h])
    return out[:96]


def main() -> int:
    site = Path(os.environ.get("SITE_ROOT") or r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")
    day = "2026-01-26"
    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else Path(bundle.idf_path or "")
    epw = Path(bundle.epw) if bundle.epw else None
    if not idf.is_file() or epw is None or not epw.is_file():
        print("NO-GO: missing idf/epw")
        return 2

    champ_hash = sha256_file(idf)
    out = site / "reports" / "eplus_gym" / "gates" / "jan26_2026_baseline"
    out.mkdir(parents=True, exist_ok=True)
    staged = stage_idf_for_period(idf, out / f"staged_{idf.name}", day, day, site_root=site)
    staged_text = staged.read_text(encoding="utf-8")
    assert "Run Simulation for Sizing Periods" in staged_text
    # Confirm No
    from eplus_native.idf_stage import disable_sizing_periods as _  # noqa: F401

    if "Yes,                      !- Run Simulation for Sizing Periods" in staged_text:
        print("NO-GO: sizing periods still Yes on staged IDF")
        return 2

    result = run_rule_episode(
        site_root=site,
        strategy_id="baseline",
        day=day,
        mode="live",
        epw=epw,
        idf=staged,
        output=out / "eplus",
        family="w2a",
        max_steps=96,
        period=f"{day}/{day}",
        weather_kind="AMY",
        verbose=False,
    )
    df = trajectory_frame(result)
    pq = out / "trajectory.parquet"
    df.to_parquet(pq, index=False)

    cal = result["meta"].get("calendar_validation") or validate_live_trajectory_calendar(
        result["rows"], expected_day=day
    )
    epw_oat = _epw_oat_c_for_day(epw, day)
    sim_oat = [float(x) for x in df["oat_c"].tolist()] if "oat_c" in df.columns else []
    oat_err = None
    if len(sim_oat) == 96:
        oat_err = sum(abs(a - b) for a, b in zip(sim_oat, epw_oat)) / 96.0

    zone_cols = [c for c in df.columns if c.startswith("zone_t_c_") or c.startswith("zone_temp_")]
    bas = [c for c in df.columns if c.startswith("zone_temp_")]
    airflow_warnings: list[str] = []
    # Scan eplus err for low airflow
    for err in (out / "eplus").rglob("*.err"):
        txt = err.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            if "airflow" in line.lower() or "flow" in line.lower() and "low" in line.lower():
                airflow_warnings.append(line.strip()[:200])
                if len(airflow_warnings) >= 20:
                    break

    ready = (
        cal.get("ok")
        and oat_err is not None
        and oat_err < 1.5
        and "facility_kw" in df.columns
        and bool(df["facility_kw"].notna().all())
        and len(bas) >= 6
        and sha256_file(idf) == champ_hash
    )
    report = {
        "day": day,
        "ready": bool(ready),
        "calendar_validation": cal,
        "oat_mae_c": oat_err,
        "n_rows": len(df),
        "facility_peak_kw": float(df["facility_kw"].max()) if "facility_kw" in df.columns else None,
        "zone_raw_or_agg_cols": zone_cols,
        "bas_agg_cols": bas,
        "champion_sha256": champ_hash,
        "champion_unchanged": sha256_file(idf) == champ_hash,
        "staged_sha256": sha256_file(staged),
        "epw_sha256": sha256_file(epw),
        "airflow_warnings_sample": airflow_warnings[:10],
        "airflow_warnings_invalidate_plant_rank": bool(airflow_warnings),
        "note": (
            "Low-airflow warnings summarized (not suppressed). "
            "If present, treat plant-power ranking with caution."
        ),
        "trajectory": str(pq),
    }
    (out / "READY.json" if ready else out / "NOGO.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (out / "gate_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("READY" if ready else "NO-GO")
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
