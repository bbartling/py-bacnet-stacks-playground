#!/usr/bin/env python3
"""Multi-day EnergyPlus demand-management farm → vibe21.dm_hourly_row.v1 Parquet.

Gaps-doc minimum (default --profile min):
  40 AMY days × baseline
  same 40 × {precool_shift, deadband_widen, chiller_off}
  10 days × full strategy set (setpoint_raise, hvac_off, precool_chiller_off)

Writes under ~/wattlab_workspace/reports/dm_hourly_farm/ (or --out-dir):
  runs/<simulation_id>/
  dm_hourly_rows.parquet
  farm_summary.json

Requires energyplus-mcp-dev via wattlab.energyplus.docker (Docker Desktop).
Fallback: --from-seed-proxy expands assets july_demand_profiles shapes across
stratified EPW days (provenance SEEDED_SHAPE_PROXY) for Unity knob demos when
Docker/WSL is down — replace with real E+ farm before claiming calibrated DR.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
PKG = TOOLS.parent
ASSETS = PKG / "assets" / "twin_b100_ops11"
TWIN_ID = "geo_b100_dual_ahu_shape_ops11"

CORE_MODES = ("baseline", "precool_shift", "deadband_widen", "chiller_off")
FULL_EXTRA = ("setpoint_raise", "hvac_off", "precool_chiller_off")

MODE_DEFAULTS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "setpoint_raise": {"delta_f": 5.0, "start_h": 14, "end_h": 16},
    "deadband_widen": {"target_db_f": 10.0, "start_h": 14, "end_h": 16},
    "chiller_off": {"start_h": 14, "end_h": 16},
    "hvac_off": {"start_h": 14, "end_h": 16},
    "precool_shift": {
        "precool_f": 2.0,
        "relax_clg_f": 5.0,
        "relax_htg_f": 2.5,
        "precool_start_h": 6,
        "precool_end_h": 12,
        "relax_end_h": 18,
    },
    "precool_chiller_off": {
        "precool_f": 2.0,
        "precool_start_h": 6,
        "precool_end_h": 12,
        "start_h": 14,
        "end_h": 16,
    },
}


def _workspace_root() -> Path:
    if Path("/data/runs").is_dir():
        return Path("/data")
    return Path.home() / "wattlab_workspace"


def _load_july():
    path = TOOLS / "july_demand_profiles_eplus.py"
    spec = importlib.util.spec_from_file_location("july_demand_profiles_eplus", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_twin_paths(
    *,
    twin_idf: Path | None = None,
    epw: Path | None = None,
    seed_from_assets: bool = True,
) -> tuple[Path, Path]:
    root = _workspace_root()
    idf = twin_idf or (root / "runs" / TWIN_ID / "model.idf")
    epw_p = epw or (root / "runs" / f"{TWIN_ID}__stage_in" / "amy.epw")
    if seed_from_assets:
        if not idf.is_file() and (ASSETS / "model.idf").is_file():
            idf.parent.mkdir(parents=True, exist_ok=True)
            idf.write_bytes((ASSETS / "model.idf").read_bytes())
        if not epw_p.is_file() and (ASSETS / "amy.epw").is_file():
            epw_p.parent.mkdir(parents=True, exist_ok=True)
            epw_p.write_bytes((ASSETS / "amy.epw").read_bytes())
            # also drop a copy next to the twin run
            alt = root / "runs" / TWIN_ID / "amy.epw"
            alt.parent.mkdir(parents=True, exist_ok=True)
            if not alt.is_file():
                alt.write_bytes(epw_p.read_bytes())
    return idf, epw_p


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_epw_day_stats(epw: Path) -> list[dict[str, Any]]:
    """One row per calendar day: max/mean DB, mean RH, max global horiz if present."""
    hours: dict[tuple[int, int, int], list[tuple[float, float, float]]] = defaultdict(list)
    for line in epw.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(",")
        if len(parts) < 8 or not parts[1].strip().isdigit():
            continue
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            db = float(parts[6])
            rh = float(parts[8]) if len(parts) > 8 and parts[8].strip() else 50.0
            ghi = float(parts[13]) if len(parts) > 13 and parts[13].strip() not in ("", "9999") else 0.0
        except ValueError:
            continue
        hours[(y, m, d)].append((db, rh, ghi))

    out: list[dict[str, Any]] = []
    for (y, m, d), vals in sorted(hours.items()):
        dbs = [v[0] for v in vals]
        rhs = [v[1] for v in vals]
        ghis = [v[2] for v in vals]
        dow = date(y, m, d).strftime("%A")
        weekend = dow in ("Saturday", "Sunday")
        tmax = max(dbs)
        if tmax < 18:
            band = "cool"
        elif tmax < 26:
            band = "mild"
        elif tmax < 32:
            band = "hot"
        else:
            band = "extreme"
        out.append(
            {
                "year": y,
                "month": m,
                "day": d,
                "iso": f"{y}-{m:02d}-{d:02d}",
                "dow": dow,
                "weekend": weekend,
                "max_db_c": round(tmax, 2),
                "mean_db_c": round(sum(dbs) / len(dbs), 2),
                "mean_rh_pct": round(sum(rhs) / len(rhs), 1),
                "max_ghi": round(max(ghis), 1),
                "band": band,
                "hourly_wx": [
                    {"hour": i + 1, "oat_c": round(db, 2), "rh_pct": round(rh, 1), "ghi": round(ghi, 1)}
                    for i, (db, rh, ghi) in enumerate(vals[:24])
                ],
            }
        )
    return out


def stratify_days(
    day_stats: list[dict[str, Any]],
    *,
    n: int = 40,
    seed: int = 21,
) -> list[dict[str, Any]]:
    """Stratify by weather band × weekday/weekend; fill to n."""
    import random

    rng = random.Random(seed)
    buckets: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in day_stats:
        buckets[(row["band"], row["weekend"])].append(row)

    # Prefer summer-ish bands first for DR story, but keep cool/mild for OAT conditioning
    order = [
        ("extreme", False),
        ("hot", False),
        ("mild", False),
        ("cool", False),
        ("extreme", True),
        ("hot", True),
        ("mild", True),
        ("cool", True),
    ]
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Round-robin until n
    while len(picked) < n:
        progressed = False
        for key in order:
            pool = [r for r in buckets.get(key, []) if r["iso"] not in seen]
            if not pool:
                continue
            choice = rng.choice(pool)
            seen.add(choice["iso"])
            picked.append(choice)
            progressed = True
            if len(picked) >= n:
                break
        if not progressed:
            # exhaust remaining days
            rest = [r for r in day_stats if r["iso"] not in seen]
            if not rest:
                break
            rng.shuffle(rest)
            for r in rest:
                if len(picked) >= n:
                    break
                seen.add(r["iso"])
                picked.append(r)
            break
    return picked[:n]


def actions_for_mode(mode: str, hour: int, kwargs: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
    """Return (actions, phase, in_dr_window) for an hour-ending stamp."""
    kw = {**MODE_DEFAULTS.get(mode, {}), **kwargs}
    start_h = int(kw.get("start_h", 14))
    end_h = int(kw.get("end_h", 16))
    pc0 = int(kw.get("precool_start_h", 6))
    pc1 = int(kw.get("precool_end_h", 12))
    rx1 = int(kw.get("relax_end_h", 18))

    empty = {
        "precool_f": 0.0,
        "relax_clg_f": 0.0,
        "relax_htg_f": 0.0,
        "deadband_target_f": None,
        "dat_delta_f": 0.0,
        "chw_avail": 1.0,
        "fan_avail": 1.0,
    }

    if mode == "baseline":
        return empty, "baseline", False

    if mode == "precool_shift":
        if pc0 < hour <= pc1:
            a = {
                **empty,
                "precool_f": float(kw.get("precool_f", 2.0)),
                "dat_delta_f": -float(kw.get("precool_f", 2.0)),
            }
            return a, "precool", True
        if pc1 < hour <= rx1:
            a = {
                **empty,
                "relax_clg_f": float(kw.get("relax_clg_f", 5.0)),
                "relax_htg_f": float(kw.get("relax_htg_f", 2.5)),
                "dat_delta_f": float(kw.get("relax_clg_f", 5.0)),
            }
            return a, "relax", True
        if rx1 < hour <= rx1 + 2:
            return empty, "recovery", False
        return empty, "baseline", False

    if mode == "precool_chiller_off":
        if pc0 < hour <= pc1:
            a = {**empty, "precool_f": float(kw.get("precool_f", 2.0)), "dat_delta_f": -float(kw.get("precool_f", 2.0))}
            return a, "precool", True
        if start_h < hour <= end_h:
            a = {**empty, "chw_avail": 0.0}
            return a, "shed", True
        if end_h < hour <= end_h + 2:
            return empty, "recovery", False
        return empty, "baseline", False

    if mode in ("setpoint_raise", "deadband_widen", "chiller_off", "hvac_off"):
        if start_h < hour <= end_h:
            a = dict(empty)
            if mode == "setpoint_raise":
                a["relax_clg_f"] = float(kw.get("delta_f", 5.0))
                a["dat_delta_f"] = float(kw.get("delta_f", 5.0))
            elif mode == "deadband_widen":
                a["deadband_target_f"] = float(kw.get("target_db_f", 10.0))
                a["dat_delta_f"] = 5.0
            elif mode == "chiller_off":
                a["chw_avail"] = 0.0
            elif mode == "hvac_off":
                a["chw_avail"] = 0.0
                a["fan_avail"] = 0.0
            return a, "shed", True
        if end_h < hour <= end_h + 2:
            return empty, "recovery", False
        return empty, "baseline", False

    return empty, "baseline", False


def strategy_id_for(mode: str) -> str:
    return {
        "baseline": "baseline",
        "setpoint_raise": "loadshed_p5f",
        "deadband_widen": "deadband_10f",
        "chiller_off": "chiller_off",
        "hvac_off": "hvac_off",
        "precool_shift": "precool_shift",
        "precool_chiller_off": "precool_chiller_off",
    }.get(mode, mode)


def build_job_list(
    days: list[dict[str, Any]],
    *,
    n_full: int = 10,
) -> list[tuple[str, dict[str, Any], str, dict[str, Any]]]:
    """(simulation_id, day_meta, mode, mode_kwargs)."""
    jobs: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []
    full_days = days[: max(0, min(n_full, len(days)))]
    full_isos = {d["iso"] for d in full_days}

    for d in days:
        for mode in CORE_MODES:
            sid = f"ops11_{d['iso']}_{strategy_id_for(mode)}"
            jobs.append((sid, d, mode, dict(MODE_DEFAULTS[mode])))
        if d["iso"] in full_isos:
            for mode in FULL_EXTRA:
                sid = f"ops11_{d['iso']}_{strategy_id_for(mode)}"
                jobs.append((sid, d, mode, dict(MODE_DEFAULTS[mode])))
    return jobs


def rows_from_case(
    *,
    simulation_id: str,
    day_meta: dict[str, Any],
    mode: str,
    mode_kwargs: dict[str, Any],
    hourly_kw: list[dict[str, Any]],
    idf_sha: str,
    epw_name: str,
    source: str = "ENERGYPLUS_SIMULATED",
    cooling_by_h: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    wx_by_h = {int(w["hour"]): w for w in day_meta.get("hourly_wx") or []}
    occupied_hours = set(range(7, 23)) if not day_meta.get("weekend") else set(range(7, 19))
    rows: list[dict[str, Any]] = []
    for pt in hourly_kw:
        hour = int(pt["hour"])
        actions, phase, in_win = actions_for_mode(mode, hour, mode_kwargs)
        wx = wx_by_h.get(hour) or {"oat_c": day_meta.get("mean_db_c"), "rh_pct": day_meta.get("mean_rh_pct"), "ghi": 0.0}
        row = {
            "schema_version": "vibe21.dm_hourly_row.v1",
            "simulation_id": simulation_id,
            "twin_run_id": TWIN_ID,
            "day": day_meta["iso"],
            "hour_ending": hour,
            "dow": day_meta["dow"],
            "oat_c": wx.get("oat_c"),
            "rh_pct": wx.get("rh_pct"),
            "ghi": wx.get("ghi"),
            "occupied": hour in occupied_hours,
            "strategy_id": strategy_id_for(mode),
            "phase": phase,
            "in_dr_window": in_win,
            "actions": actions,
            "targets": {
                "facility_kw": float(pt["kw"]),
                "cooling_kw": None if not cooling_by_h else cooling_by_h.get(hour),
                "max_zone_temp_c": None,
                "unmet_hours_flag": False,
            },
            "provenance": {
                "source": source,
                "idf_sha256": idf_sha,
                "epw": epw_name,
                "mode": mode,
            },
        }
        rows.append(row)
    return rows


def write_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd

        flat = []
        for r in rows:
            flat.append(
                {
                    "schema_version": r["schema_version"],
                    "simulation_id": r["simulation_id"],
                    "twin_run_id": r["twin_run_id"],
                    "day": r["day"],
                    "hour_ending": r["hour_ending"],
                    "dow": r["dow"],
                    "oat_c": r["oat_c"],
                    "rh_pct": r["rh_pct"],
                    "ghi": r.get("ghi"),
                    "occupied": r["occupied"],
                    "strategy_id": r["strategy_id"],
                    "phase": r["phase"],
                    "in_dr_window": r["in_dr_window"],
                    "precool_f": r["actions"]["precool_f"],
                    "relax_clg_f": r["actions"]["relax_clg_f"],
                    "relax_htg_f": r["actions"]["relax_htg_f"],
                    "deadband_target_f": r["actions"]["deadband_target_f"],
                    "dat_delta_f": r["actions"]["dat_delta_f"],
                    "chw_avail": r["actions"]["chw_avail"],
                    "fan_avail": r["actions"]["fan_avail"],
                    "facility_kw": r["targets"]["facility_kw"],
                    "cooling_kw": r["targets"]["cooling_kw"],
                    "max_zone_temp_c": r["targets"]["max_zone_temp_c"],
                    "unmet_hours_flag": r["targets"]["unmet_hours_flag"],
                    "provenance_source": r["provenance"]["source"],
                    "idf_sha256": r["provenance"]["idf_sha256"],
                    "epw": r["provenance"]["epw"],
                    "mode": r["provenance"]["mode"],
                }
            )
        pd.DataFrame(flat).to_parquet(path, index=False)
    except Exception:
        # fallback jsonl if pyarrow missing
        alt = path.with_suffix(".jsonl")
        with alt.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        path.write_text(json.dumps({"error": "parquet_unavailable", "jsonl": str(alt), "n_rows": len(rows)}), encoding="utf-8")


def seed_proxy_farm(
    days: list[dict[str, Any]],
    jobs: list[tuple[str, dict[str, Any], str, dict[str, Any]]],
    *,
    idf_sha: str,
    epw_name: str,
) -> list[dict[str, Any]]:
    """Shape-proxy from packaged july_demand_profiles — Unity interim only."""
    seed_path = ASSETS / "july_demand_profiles.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    cases = seed.get("cases") or {}
    mode_to_label = {
        "baseline": "weekday_baseline",
        "setpoint_raise": "weekday_loadshed_p5f",
        "deadband_widen": "weekday_deadband_10f",
        "chiller_off": "weekday_chiller_off",
        "hvac_off": "weekday_hvac_off",
        "precool_shift": "weekday_precool_shift",
        "precool_chiller_off": "weekday_precool_chiller_off",
    }
    base_case = cases.get("weekday_baseline") or {}
    base_h = {int(p["hour"]): float(p["kw"]) for p in base_case.get("hourly_kw") or []}
    base_peak = max(base_h.values()) if base_h else 400.0
    ref_tmax = float((seed.get("days_selected") or {}).get("weekday", {}).get("max_db_c") or 36.9)

    rows: list[dict[str, Any]] = []
    for sid, day_meta, mode, kwargs in jobs:
        label = mode_to_label.get(mode, "weekday_baseline")
        src = cases.get(label) or cases.get("weekday_baseline") or {}
        shape = {int(p["hour"]): float(p["kw"]) for p in src.get("hourly_kw") or []}
        if not shape:
            continue
        # Scale by day max DB vs reference hot day (rough OA conditioning)
        scale = 0.55 + 0.45 * (float(day_meta["max_db_c"]) / ref_tmax)
        if day_meta.get("weekend"):
            scale *= 0.72
        hourly = [{"hour": h, "kw": round(kw * scale, 3)} for h, kw in sorted(shape.items())]
        # weekend baseline: prefer weekend seed if baseline
        if mode == "baseline" and day_meta.get("weekend") and cases.get("weekend_baseline"):
            wshape = {int(p["hour"]): float(p["kw"]) for p in cases["weekend_baseline"].get("hourly_kw") or []}
            if wshape:
                wscale = 0.55 + 0.45 * (float(day_meta["max_db_c"]) / float(
                    (seed.get("days_selected") or {}).get("weekend", {}).get("max_db_c") or 34.3
                ))
                hourly = [{"hour": h, "kw": round(kw * wscale, 3)} for h, kw in sorted(wshape.items())]
        rows.extend(
            rows_from_case(
                simulation_id=sid,
                day_meta=day_meta,
                mode=mode,
                mode_kwargs=kwargs,
                hourly_kw=hourly,
                idf_sha=idf_sha,
                epw_name=epw_name,
                source="SEEDED_SHAPE_PROXY",
            )
        )
    _ = base_peak  # reserved for future relative metrics
    return rows


def run_eplus_jobs(
    july,
    twin: Path,
    epw: Path,
    out_dir: Path,
    jobs: list[tuple[str, dict[str, Any], str, dict[str, Any]]],
    *,
    reuse: bool,
    idf_sha: str,
    engine: str = "auto",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runs = out_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    for sid, day_meta, mode, kwargs in jobs:
        case_dir = runs / f"sim_{sid}"
        csv_path = case_dir / "eplusout.csv"
        if not csv_path.is_file():
            # also accept runs/<sid>/eplusout.csv from older layout
            alt = runs / sid / "eplusout.csv"
            if alt.is_file():
                csv_path = alt
                case_dir = runs / sid
        if reuse and csv_path.is_file():
            print(f"reuse {sid}", flush=True)
            hourly = july.parse_hourly_facility_kw(csv_path)
        else:
            print(f"sim {sid} mode={mode} engine={engine} …", flush=True)
            day_run = {
                "year": day_meta["year"],
                "month": day_meta["month"],
                "day": day_meta["day"],
                "dow": day_meta["dow"],
                "max_db_c": day_meta["max_db_c"],
            }
            result = july.run_case(
                twin,
                epw,
                runs,
                sid,
                day_meta=day_run,
                mode=mode,
                mode_kwargs=kwargs,
                engine=engine,
            )
            hourly = result.get("hourly_kw") or []
            if not hourly:
                print(f"  WARN empty hourly rc={result.get('rc')}", flush=True)
            else:
                print(
                    f"  peak={result.get('peak_kw')} event={result.get('event_mean_kw_14_16')}",
                    flush=True,
                )
            csv_path = Path(result["eplusout_csv"]) if result.get("eplusout_csv") else csv_path
        rows.extend(
            rows_from_case(
                simulation_id=sid,
                day_meta=day_meta,
                mode=mode,
                mode_kwargs=kwargs,
                hourly_kw=hourly,
                idf_sha=idf_sha,
                epw_name=epw.name,
                source="ENERGYPLUS_SIMULATED",
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--twin-idf", type=Path, default=None)
    ap.add_argument("--epw", type=Path, default=None)
    ap.add_argument("--n-days", type=int, default=40)
    ap.add_argument("--n-full", type=int, default=10, help="Days that also get full strategy extras")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--smoke", action="store_true", help="3 days × core modes only")
    ap.add_argument("--reuse-existing", action="store_true")
    ap.add_argument(
        "--from-seed-proxy",
        action="store_true",
        help="No Docker: expand july seed shapes across stratified EPW days (SEEDED_SHAPE_PROXY)",
    )
    ap.add_argument(
        "--engine",
        choices=("auto", "native", "docker"),
        default="auto",
        help="EnergyPlus backend (auto→native if C:\\EnergyPlusV26-1-0 exists)",
    )
    ap.add_argument("--write-jsonl", action="store_true")
    args = ap.parse_args(argv)

    root = _workspace_root()
    out_dir = args.out_dir or (root / "reports" / "dm_hourly_farm")
    out_dir.mkdir(parents=True, exist_ok=True)

    twin, epw = resolve_twin_paths(twin_idf=args.twin_idf, epw=args.epw)
    if not twin.is_file() or not epw.is_file():
        print("missing idf/epw", twin, epw, file=sys.stderr)
        return 2

    idf_sha = sha256_file(twin)
    day_stats = parse_epw_day_stats(epw)
    n_days = 3 if args.smoke else args.n_days
    n_full = 0 if args.smoke else args.n_full
    days = stratify_days(day_stats, n=n_days, seed=args.seed)
    jobs = build_job_list(days, n_full=n_full)
    if args.smoke:
        # core only already; trim duplicate extras
        jobs = [j for j in jobs if j[2] in CORE_MODES]

    engine = args.engine
    if engine == "auto":
        ml = Path(__file__).resolve().parent.parent / "ml"
        if str(ml) not in sys.path:
            sys.path.insert(0, str(ml))
        try:
            from native_energyplus import native_energyplus_available

            engine = "native" if native_energyplus_available() else "docker"
        except Exception:
            engine = "docker"

    print(f"days={len(days)} jobs={len(jobs)} engine={engine} out={out_dir}", flush=True)
    july = _load_july()

    if args.from_seed_proxy:
        rows = seed_proxy_farm(days, jobs, idf_sha=idf_sha, epw_name=epw.name)
        source = "SEEDED_SHAPE_PROXY"
    else:
        try:
            rows = run_eplus_jobs(
                july,
                twin,
                epw,
                out_dir,
                jobs,
                reuse=args.reuse_existing,
                idf_sha=idf_sha,
                engine=engine,
            )
            source = "ENERGYPLUS_SIMULATED"
        except Exception as exc:
            print(
                f"E+ farm failed ({exc}); hint: --engine native or --from-seed-proxy",
                file=sys.stderr,
            )
            return 3

    pq = out_dir / "dm_hourly_rows.parquet"
    write_parquet(rows, pq)
    if args.write_jsonl:
        jl = out_dir / "dm_hourly_rows.jsonl"
        with jl.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    summary = {
        "twin_id": TWIN_ID,
        "n_days": len(days),
        "n_jobs": len(jobs),
        "n_rows": len(rows),
        "source": source,
        "engine": engine if not args.from_seed_proxy else None,
        "days": [{"iso": d["iso"], "band": d["band"], "max_db_c": d["max_db_c"], "dow": d["dow"]} for d in days],
        "parquet": str(pq),
        "idf_sha256": idf_sha,
        "epw": str(epw),
    }
    (out_dir / "farm_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_rows": len(rows), "source": source, "engine": summary.get("engine"), "parquet": str(pq)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
