#!/usr/bin/env python3
"""Score a WattLab/E+ run vs B100 area-weighted bills (no prototype_area_scale).

Skips sizing-period Monthly rows by keeping the last 12 positive calendar months.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

J_TO_KWH = 1 / 3.6e6
J_TO_THERM = 1 / 1.05506e8
KWH_TO_KBTU = 3.412
THERM_TO_KBTU = 100.0


def last12_monthly(series: pd.Series) -> pd.Series:
    s = series.dropna().astype(float)
    s = s[s > 0]
    if len(s) > 12:
        s = s.iloc[-12:]
    return s


def score_run(
    eplusout_csv: Path,
    bills_csv: Path,
    *,
    area_ft2: float = 140_000.0,
    run_id: str | None = None,
) -> dict:
    bills = list(csv.DictReader(open(bills_csv)))
    bk = sum(float(r["kwh"]) for r in bills)
    bt = sum(float(r["therms"]) for r in bills)
    bill_eui = (bk * KWH_TO_KBTU + bt * THERM_TO_KBTU) / area_ft2

    df = pd.read_csv(eplusout_csv)
    elec_c = "Electricity:Facility [J](Monthly)"
    gas_c = [c for c in df.columns if "NaturalGas:Facility" in c and "Monthly" in c][0]
    e = float(last12_monthly(df[elec_c]).sum()) * J_TO_KWH
    g = float(last12_monthly(df[gas_c]).sum()) * J_TO_THERM
    eui = (e * KWH_TO_KBTU + g * THERM_TO_KBTU) / area_ft2

    out = {
        "run_id": run_id or eplusout_csv.parent.name,
        "area_scale": 1.0,
        "area_ft2": area_ft2,
        "model_kwh": round(e, 1),
        "model_therms": round(g, 1),
        "model_site_eui": round(eui, 1),
        "bill_kwh": bk,
        "bill_therms": bt,
        "bill_site_eui": round(bill_eui, 1),
        "elec_delta_pct": round((e - bk) / bk * 100, 1),
        "gas_delta_pct": round((g - bt) / bt * 100, 1),
        "eui_delta_pct": round((eui - bill_eui) / bill_eui * 100, 1),
        "fuel_mix_score": round(
            abs((e - bk) / bk) + abs((g - bt) / bt), 3
        ),  # lower better
    }
    try:
        from wattlab.benchmarks import compare_eui

        out["model_peer"] = compare_eui(eui, "office")
    except Exception as exc:  # pragma: no cover
        out["model_peer_error"] = str(exc)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("eplusout_csv")
    p.add_argument("--bills", required=True)
    p.add_argument("--area", type=float, default=140000)
    p.add_argument("--run-id")
    p.add_argument("--out", help="write JSON scorecard")
    args = p.parse_args()
    sc = score_run(
        Path(args.eplusout_csv),
        Path(args.bills),
        area_ft2=args.area,
        run_id=args.run_id,
    )
    text = json.dumps(sc, indent=2) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
