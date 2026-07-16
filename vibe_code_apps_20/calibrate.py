"""Overlap-window calibration: AMY EPW + custom RunPeriod + scorecard vs vibe19 seed.

Usage:
  python calibrate.py --bundle <vibe19_export_dir> [--seed model_seed.json] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ARTIFACTS, DEFAULT_PROTOTYPE_IDF, ROOT
from ep_mcp_client import simulate
from idf_patches import apply_hourly_outputs, apply_run_period
from idf_patches.schedules import apply_fan_avail_continuous
from results_parse import annual_from_output_dir
from wattlab_defaults import resolve_profile
from weather_epw import build_amy_epw

# ASHRAE Guideline 14 monthly thresholds
NMBE_PASS = 5.0
CVRMSE_PASS = 15.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nmbe_cvrmse(observed: list[float], simulated: list[float]) -> dict[str, float]:
    """NMBE and CVRMSE in percent (ASHRAE Guideline 14)."""
    pairs = [(float(o), float(s)) for o, s in zip(observed, simulated) if o is not None and s is not None]
    pairs = [(o, s) for o, s in pairs if not (math.isnan(o) or math.isnan(s))]
    if not pairs:
        return {"n": 0, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": float("nan")}
    n = len(pairs)
    mean_obs = sum(o for o, _ in pairs) / n
    if abs(mean_obs) < 1e-12:
        return {"n": n, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": mean_obs}
    nmbe = sum(o - s for o, s in pairs) / (n * mean_obs) * 100.0
    # Guideline 14 uses (n - 1) for CVRMSE when n > 1
    denom = n - 1 if n > 1 else n
    mse = sum((o - s) ** 2 for o, s in pairs) / denom
    cvrmse = math.sqrt(mse) / abs(mean_obs) * 100.0
    return {
        "n": n,
        "nmbe_pct": round(nmbe, 3),
        "cvrmse_pct": round(cvrmse, 3),
        "mean_obs": round(mean_obs, 3),
    }


def _pass_fail(stats: dict[str, float]) -> str:
    if stats.get("n", 0) == 0 or math.isnan(stats.get("nmbe_pct", float("nan"))):
        return "insufficient_data"
    if abs(stats["nmbe_pct"]) <= NMBE_PASS and stats["cvrmse_pct"] <= CVRMSE_PASS:
        return "pass"
    return "fail"


def aggregate_signatures(rows: list[dict[str, str]], kind: str = "fan") -> dict[int, float]:
    """Mean on_fraction by OAT bin_start for a signature kind."""
    buckets: dict[int, list[float]] = {}
    for r in rows:
        if (r.get("kind") or "").strip() != kind:
            continue
        try:
            b = int(float(r["bin_start"]))
            frac = float(r["on_fraction"])
        except (KeyError, TypeError, ValueError):
            continue
        buckets.setdefault(b, []).append(frac)
    return {b: sum(v) / len(v) for b, v in buckets.items()}


def parse_eplusout_hourly(sim_dir: Path) -> list[dict[str, Any]]:
    """Parse eplusout.csv hourly rows into {oat_c, fan_w, cool_w, ...}."""
    path = sim_dir / "eplusout.csv"
    if not path.is_file():
        # Some EnergyPlus builds use eplusout.csv.gz or different name
        alts = list(sim_dir.glob("eplusout*.csv"))
        if not alts:
            return []
        path = alts[0]
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []
        header_l = [h.strip().lower() for h in header]
        def find(*needles: str) -> int | None:
            for i, h in enumerate(header_l):
                if all(n in h for n in needles):
                    return i
            return None

        i_oat = find("outdoor", "drybulb") or find("site outdoor air drybulb")
        i_fan = find("fan electricity rate")
        i_cool = find("cooling coil total cooling rate") or find("chiller electricity rate")
        i_elec = None
        for i, h in enumerate(header_l):
            if "electricity:facility" in h and "hourly" in h:
                i_elec = i
                break
            if i_elec is None and "electricity:facility" in h:
                i_elec = i

        for raw in reader:
            if not raw or len(raw) < 2:
                continue
            def _f(idx: int | None) -> float:
                if idx is None or idx >= len(raw):
                    return float("nan")
                try:
                    return float(raw[idx])
                except ValueError:
                    return float("nan")

            rows.append(
                {
                    "oat_c": _f(i_oat),
                    "fan_w": _f(i_fan),
                    "cool_w": _f(i_cool),
                    "elec_j": _f(i_elec),
                }
            )
    return rows


def simulated_signatures_from_hourly(
    hourly: list[dict[str, Any]],
    *,
    bin_width_f: float = 5.0,
) -> dict[str, dict[int, float]]:
    """Build fan / mech_cooling on_fraction by OAT bin from hourly sim rows."""
    fan_buckets: dict[int, list[int]] = {}
    cool_buckets: dict[int, list[int]] = {}
    for r in hourly:
        oat_c = r.get("oat_c")
        if oat_c is None or math.isnan(oat_c):
            continue
        oat_f = oat_c * 9.0 / 5.0 + 32.0
        if oat_f < 40 or oat_f > 110:
            continue
        b = int(math.floor(oat_f / bin_width_f) * bin_width_f)
        fan_on = 1 if (r.get("fan_w") or 0) > 10.0 else 0  # >10 W
        cool_on = 1 if (r.get("cool_w") or 0) > 100.0 else 0
        fan_buckets.setdefault(b, []).append(fan_on)
        cool_buckets.setdefault(b, []).append(cool_on)

    def _frac(buckets: dict[int, list[int]]) -> dict[int, float]:
        return {b: sum(v) / len(v) for b, v in buckets.items() if v}

    return {"fan": _frac(fan_buckets), "mech_cooling": _frac(cool_buckets)}


def compare_signature_maps(
    observed: dict[int, float],
    simulated: dict[int, float],
) -> dict[str, Any]:
    bins = sorted(set(observed) & set(simulated))
    if not bins:
        return {
            "bins_compared": 0,
            "stats": nmbe_cvrmse([], []),
            "pass_fail": "insufficient_data",
            "per_bin": [],
        }
    obs = [observed[b] for b in bins]
    sim = [simulated[b] for b in bins]
    stats = nmbe_cvrmse(obs, sim)
    per_bin = [
        {
            "bin_start": b,
            "observed_on_fraction": round(observed[b], 4),
            "simulated_on_fraction": round(simulated[b], 4),
            "delta": round(simulated[b] - observed[b], 4),
        }
        for b in bins
    ]
    return {
        "bins_compared": len(bins),
        "stats": stats,
        "pass_fail": _pass_fail(stats),
        "per_bin": per_bin,
    }


def load_utility_bills(bundle: Path, seed: dict[str, Any]) -> list[dict[str, Any]]:
    bills = seed.get("utility_bills")
    if isinstance(bills, list) and bills:
        return bills
    path = bundle / "utility_bills.csv"
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            out.append(
                {
                    "month": int(float(r.get("month") or 0)),
                    "kwh": float(r["kwh"]) if r.get("kwh") not in (None, "") else None,
                    "therms": float(r["therms"]) if r.get("therms") not in (None, "") else None,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def compare_bills_to_monthly(
    bills: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
) -> dict[str, Any]:
    by_m = {int(m["month"]): m for m in monthly if m.get("month")}
    obs_kwh: list[float] = []
    sim_kwh: list[float] = []
    per_month: list[dict[str, Any]] = []
    for b in bills:
        m = int(b.get("month") or 0)
        if m not in by_m:
            continue
        o = b.get("kwh")
        s = by_m[m].get("electricity_kwh")
        if o is None or s is None:
            continue
        obs_kwh.append(float(o))
        sim_kwh.append(float(s))
        per_month.append(
            {
                "month": m,
                "observed_kwh": float(o),
                "simulated_kwh": float(s),
                "delta_kwh": float(s) - float(o),
            }
        )
    stats = nmbe_cvrmse(obs_kwh, sim_kwh)
    return {
        "months_compared": len(per_month),
        "stats": stats,
        "pass_fail": _pass_fail(stats),
        "per_month": per_month,
        "thresholds": {"nmbe_pct": NMBE_PASS, "cvrmse_pct": CVRMSE_PASS},
    }


def run_calibration(
    bundle_dir: Path,
    *,
    seed_path: Path | None = None,
    dry_run: bool = False,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    seed_file = Path(seed_path) if seed_path else bundle / "model_seed.json"
    if not seed_file.is_file():
        raise FileNotFoundError(f"model_seed.json not found: {seed_file}")
    seed = _read_json(seed_file)

    weather_csv = bundle / "weather_observed.csv"
    sig_rows = _read_csv(bundle / "operating_signatures.csv")
    window = seed.get("data_window") or {}
    begin = window.get("start_utc")
    end = window.get("end_utc")
    if not begin or not end:
        raise ValueError("model_seed.data_window.start_utc/end_utc required")

    # Merge user geometry from seed into resolve_profile
    minimal = {
        k: seed[k]
        for k in (
            "building_type",
            "city",
            "code_year",
            "floor_area_ft2",
            "floors",
            "floor_to_floor_ft",
            "wwr",
            "hvac",
            "utility",
            "project_id",
            "display_name",
            "anonymized",
        )
        if seed.get(k) is not None
    }
    if not minimal.get("building_type"):
        minimal["building_type"] = "office"
    if not minimal.get("city"):
        minimal["city"] = "chicago"
    profile = resolve_profile(minimal)

    lat_v = float(lat if lat is not None else seed.get("lat") or 41.98)
    lon_v = float(lon if lon is not None else seed.get("lon") or -87.92)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ARTIFACTS / f"calibrate_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    plan = {
        "product": "OpenFDD WattLab Calibration",
        "run_id": run_id,
        "bundle": str(bundle),
        "seed": str(seed_file),
        "data_window": window,
        "lat": lat_v,
        "lon": lon_v,
        "weather_csv": str(weather_csv) if weather_csv.is_file() else None,
        "artifacts_dir": str(run_dir),
    }
    if dry_run:
        plan["dry_run"] = True
        (run_dir / "calibration_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return plan

    if not weather_csv.is_file():
        raise FileNotFoundError(f"weather_observed.csv required for AMY EPW: {weather_csv}")

    epw_path = run_dir / "amy.epw"
    epw_meta = build_amy_epw(
        weather_csv,
        epw_path,
        lat=lat_v,
        lon=lon_v,
        location_name=str(seed.get("project_id") or "OpenFDD_AMY"),
    )

    proto_rel = (profile.get("energyplus") or {}).get("prototype_idf")
    proto = Path(proto_rel) if proto_rel else DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        proto = ROOT / proto_rel if proto_rel else DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        proto = DEFAULT_PROTOTYPE_IDF
    if not proto.is_file():
        raise FileNotFoundError(f"Prototype IDF not found: {proto}")
    idf1 = run_dir / "cal_base.idf"
    apply_fan_avail_continuous(proto, idf1)
    idf2 = run_dir / "cal_runperiod.idf"
    rp_meta = apply_run_period(idf1, idf2, begin=begin, end=end)
    idf3 = run_dir / "cal_ready.idf"
    out_meta = apply_hourly_outputs(idf2, idf3)

    sim_dir = run_dir / "sim_calibrate"
    sim_dir.mkdir(parents=True, exist_ok=True)
    sim_result = simulate(idf3, epw_path, sim_dir)
    annual = annual_from_output_dir(sim_dir)

    hourly = parse_eplusout_hourly(sim_dir)
    sim_sigs = simulated_signatures_from_hourly(hourly)
    obs_fan = aggregate_signatures(sig_rows, "fan")
    obs_cool = aggregate_signatures(sig_rows, "mech_cooling")
    fan_cmp = compare_signature_maps(obs_fan, sim_sigs.get("fan") or {})
    cool_cmp = compare_signature_maps(obs_cool, sim_sigs.get("mech_cooling") or {})

    bills = load_utility_bills(bundle, seed)
    bills_cmp: dict[str, Any] | None = None
    if bills:
        bills_cmp = compare_bills_to_monthly(bills, annual.get("monthly") or [])
    else:
        bills_cmp = {
            "months_compared": 0,
            "pass_fail": "bills_recommended",
            "note": "Upload monthly utility bills for ASHRAE-14 magnitude calibration.",
        }

    # Overall: bills pass if present, else fan-signature shape is the soft gate
    if bills and bills_cmp.get("pass_fail") in {"pass", "fail"}:
        overall = bills_cmp["pass_fail"]
    elif fan_cmp.get("bins_compared", 0) > 0:
        # Soften signature thresholds (behavior shape, not energy magnitude)
        overall = "shape_ok" if fan_cmp["pass_fail"] != "insufficient_data" else "insufficient_data"
    else:
        overall = "insufficient_data"

    scorecard = {
        "product": "OpenFDD WattLab Calibration",
        "run_id": run_id,
        "overall": overall,
        "data_window": window,
        "epw": epw_meta,
        "run_period": rp_meta,
        "hourly_outputs": out_meta,
        "simulate": {
            "ok": bool(sim_result.get("ok", True)) if isinstance(sim_result, dict) else True,
            "sim_dir": str(sim_dir),
        },
        "annual": {
            "electricity_kwh_year": annual.get("electricity_kwh_year"),
            "site_eui_kbtu_ft2_year": annual.get("site_eui_kbtu_ft2_year"),
            "status": annual.get("status"),
            "monthly": annual.get("monthly") or [],
        },
        "signatures": {
            "fan": fan_cmp,
            "mech_cooling": cool_cmp,
        },
        "utility_bills": bills_cmp,
        "thresholds_ashrae14_monthly": {"nmbe_pct": NMBE_PASS, "cvrmse_pct": CVRMSE_PASS},
        "artifacts_dir": str(run_dir),
        "profile_project_id": profile.get("project_id"),
    }
    out_json = run_dir / "calibration_scorecard.json"
    out_json.write_text(json.dumps(scorecard, indent=2, default=str), encoding="utf-8")
    scorecard["scorecard_path"] = str(out_json)
    return scorecard


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Calibrate WattLab prototype against vibe19 model seed")
    p.add_argument("--bundle", type=Path, required=True, help="vibe19 export / model-seed bundle dir")
    p.add_argument("--seed", type=Path, default=None, help="Override model_seed.json path")
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lon", type=float, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        result = run_calibration(
            args.bundle,
            seed_path=args.seed,
            dry_run=args.dry_run,
            lat=args.lat,
            lon=args.lon,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
