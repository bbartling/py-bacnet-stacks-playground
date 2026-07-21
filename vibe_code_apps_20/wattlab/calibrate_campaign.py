"""Turnkey AMY + ASHRAE G14 calibrate campaign (bill months → score → Twin publish).

Does not invent site geometry. Requires human fields (building_type, city,
floor_area_ft2, lat/lon) and monthly ``utility_bills.csv`` aligned to the AMY window.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.config import PROTOTYPE_AREA_FT2_NOMINAL


def _load_bills_csv(path: Path) -> list[dict[str, Any]]:
    import csv

    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            month = str(r.get("month") or r.get("period") or "")[:7]
            if not month:
                continue
            entry: dict[str, Any] = {"month": month, "period": month}
            if r.get("kwh") not in (None, ""):
                entry["kwh"] = float(r["kwh"])
            if r.get("therms") not in (None, ""):
                entry["therms"] = float(r["therms"])
            rows.append(entry)
    return rows


def data_window_from_bill_months(months: list[str]) -> dict[str, str]:
    """Inclusive UTC window covering first→last ``YYYY-MM`` bill months."""
    keys = sorted({str(m)[:7] for m in months if m and len(str(m)) >= 7})
    if not keys:
        raise ValueError("NEEDS_INPUT: no bill months to derive data_window")
    y0, m0 = int(keys[0][:4]), int(keys[0][5:7])
    y1, m1 = int(keys[-1][:4]), int(keys[-1][5:7])
    start = date(y0, m0, 1)
    # End = last day of end month
    if m1 == 12:
        end = date(y1 + 1, 1, 1)
    else:
        end = date(y1, m1 + 1, 1)
    from datetime import timedelta

    end = end - timedelta(days=1)
    return {
        "start_utc": f"{start.isoformat()}T00:00:00Z",
        "end_utc": f"{end.isoformat()}T23:59:59Z",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bill_months_first": keys[0],
        "bill_months_last": keys[-1],
        "n_bill_months": str(len(keys)),
    }


def scale_monthly_energy(
    monthly: list[dict[str, Any]],
    *,
    area_scale: float | None,
) -> list[dict[str, Any]]:
    """Scale prototype monthly kWh/therms toward site for G14 absolute compare."""
    from wattlab.calibrate import scale_monthly_energy as _scale

    return _scale(monthly, area_scale=area_scale)


def run_calibrate_campaign(
    *,
    bundle: Path,
    bills_csv: Path | None = None,
    lat: float | None = None,
    lon: float | None = None,
    seed_path: Path | None = None,
    dry_run: bool = False,
    validation_months: int = 0,
    allow_area_scaled_g14: bool = True,
    hard_size: dict[str, float] | None = None,
    fetch_open_meteo_if_missing: bool = True,
) -> dict[str, Any]:
    """Bills → data_window → AMY (if needed) → ``run_calibration`` → Twin publish."""
    from wattlab.calibrate import load_utility_bills, run_calibration, _read_json
    from wattlab.twin import maybe_build_amy_from_open_meteo

    bundle = Path(bundle)
    work = bundle
    if bundle.is_file() and bundle.suffix.lower() == ".zip":
        from wattlab.seed import load_bundle

        loaded = load_bundle(bundle)
        for name in ("model_seed.json", "weather_observed.csv", "operating_signatures.csv"):
            p = loaded.files.get(name)
            if p is not None:
                work = Path(p).parent
                break

    seed_file = Path(seed_path) if seed_path else work / "model_seed.json"
    if not seed_file.is_file():
        raise FileNotFoundError(f"model_seed.json not found: {seed_file}")
    seed = _read_json(seed_file)

    # Prefer explicit bills CSV; else dump utility_bills
    bills: list[dict[str, Any]] = []
    if bills_csv is not None and Path(bills_csv).is_file():
        bills = _load_bills_csv(Path(bills_csv))
        dest = work / "utility_bills.csv"
        if Path(bills_csv).resolve() != dest.resolve():
            shutil.copy2(bills_csv, dest)
    else:
        bills = load_utility_bills(work, seed)

    if not bills:
        raise ValueError(
            "NEEDS_INPUT: monthly utility_bills.csv required for G14 campaign "
            "(wattlab seed import-bills … or --bills)"
        )

    months = [str(b.get("month") or b.get("period") or "")[:7] for b in bills]
    window = data_window_from_bill_months(months)
    seed = dict(seed)
    seed["data_window"] = {**(seed.get("data_window") or {}), **window}
    if lat is not None:
        seed["lat"] = float(lat)
    if lon is not None:
        seed["lon"] = float(lon)
    # Persist updated seed for calibrate
    campaign_seed = work / "model_seed_campaign.json"
    campaign_seed.write_text(json.dumps(seed, indent=2), encoding="utf-8")

    area_ft2 = float(seed.get("conditioned_floor_area_ft2") or seed.get("floor_area_ft2") or 0)
    area_scale_nominal = (
        area_ft2 / PROTOTYPE_AREA_FT2_NOMINAL if area_ft2 > 0 else None
    )

    plan: dict[str, Any] = {
        "product": "OpenFDD WattLab Calibrate Campaign",
        "bundle": str(work),
        "data_window": window,
        "n_bills": len(bills),
        "prototype_area_ft2_nominal": PROTOTYPE_AREA_FT2_NOMINAL,
        "target_floor_area_ft2": area_ft2 or None,
        "prototype_area_scale": area_scale_nominal,
        "allow_area_scaled_g14": allow_area_scaled_g14,
        "hard_size": hard_size,
        "honesty": (
            "G14 uses AMY weather aligned to bill months. Absolute kWh compare applies "
            "prototype_area_scale when allow_area_scaled_g14 — this is screening math on "
            "unscaled 5Zone geometry, not a site CAD model. Do not claim calibrated ROI "
            "until G14 passes with honest stamps (or document failure → ESCO proxies)."
        ),
    }
    if dry_run:
        plan["dry_run"] = True
        return plan

    has_wx = (work / "weather_observed.csv").is_file()
    amy_meta = None
    if fetch_open_meteo_if_missing and not has_wx:
        amy_meta = maybe_build_amy_from_open_meteo(
            seed, work, has_observed_weather=False
        )
        if amy_meta is None:
            raise ValueError(
                "NEEDS_INPUT: weather_observed.csv missing and Open-Meteo AMY could not "
                "be built (need lat/lon + data_window)"
            )
        plan["open_meteo"] = amy_meta

    scorecard = run_calibration(
        work,
        seed_path=campaign_seed,
        dry_run=False,
        lat=float(seed["lat"]) if seed.get("lat") is not None else None,
        lon=float(seed["lon"]) if seed.get("lon") is not None else None,
        validation_months=validation_months,
        area_scale_for_g14=(
            area_scale_nominal if allow_area_scaled_g14 else None
        ),
        publish_studio=True,
        hard_size=hard_size,
    )
    plan["scorecard"] = {
        "run_id": scorecard.get("run_id"),
        "status": scorecard.get("status"),
        "overall": scorecard.get("overall"),
        "pass_fail": (scorecard.get("utility_bills") or {}).get("pass_fail"),
        "scorecard_path": scorecard.get("scorecard_path"),
        "studio_run_dir": scorecard.get("studio_run_dir"),
    }
    plan["calibration_status"] = scorecard.get("status")
    plan["ok"] = True
    return plan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="AMY + G14 calibrate campaign (bill months → Twin publish)"
    )
    p.add_argument("--bundle", type=Path, required=True, help="WattLab dump dir or zip")
    p.add_argument("--bills", type=Path, default=None, help="utility_bills.csv (YYYY-MM)")
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lon", type=float, default=None)
    p.add_argument("--seed", type=Path, default=None)
    p.add_argument("--validation-months", type=int, default=0)
    p.add_argument(
        "--no-area-scaled-g14",
        action="store_true",
        help="Compare raw prototype kWh to site bills (almost always wrong for large sites)",
    )
    p.add_argument("--cooling-tons", type=float, default=None)
    p.add_argument("--fan-hp", type=float, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    hard: dict[str, float] | None = None
    if args.cooling_tons or args.fan_hp:
        hard = {}
        if args.cooling_tons:
            hard["cooling_tons"] = float(args.cooling_tons)
        if args.fan_hp:
            hard["fan_hp"] = float(args.fan_hp)

    try:
        result = run_calibrate_campaign(
            bundle=args.bundle,
            bills_csv=args.bills,
            lat=args.lat,
            lon=args.lon,
            seed_path=args.seed,
            dry_run=args.dry_run,
            validation_months=args.validation_months,
            allow_area_scaled_g14=not args.no_area_scaled_g14,
            hard_size=hard,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
