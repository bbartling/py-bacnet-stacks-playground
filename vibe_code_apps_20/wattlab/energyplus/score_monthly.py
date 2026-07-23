"""Score an EnergyPlus monthly eplusout.csv vs utility bills (area_scale=1).

Skips sizing-period Monthly rows by keeping the last 12 positive calendar months.
Use after site-scale geometry (``wattlab geo-idf``) — never apply prototype_area_scale.

    wattlab score-monthly runs/<id>/eplusout.csv \\
      --bills reports/utility_bills.csv --area-ft2 140000
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

J_TO_KWH = 1 / 3.6e6
J_TO_THERM = 1 / 1.05506e8
KWH_TO_KBTU = 3.412
THERM_TO_KBTU = 100.0
MCF_TO_THERM = 10.37  # approx HHV; override via --therms-per-mcf


def last12_monthly(series: pd.Series) -> pd.Series:
    s = series.dropna().astype(float)
    s = s[s > 0]
    if len(s) > 12:
        s = s.iloc[-12:]
    return s


def _bill_totals(
    bills_csv: Path,
    *,
    therms_per_mcf: float = MCF_TO_THERM,
) -> tuple[float, float]:
    """Return (kWh, therms) from a bills CSV (flexible headers)."""
    with Path(bills_csv).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"empty bills CSV: {bills_csv}")
    keys = {k.lower(): k for k in rows[0].keys()}

    def col(*names: str) -> str | None:
        for n in names:
            if n in keys:
                return keys[n]
        return None

    kwh_c = col("kwh", "electricity_kwh", "elec_kwh", "usage_kwh")
    therm_c = col("therms", "therm", "gas_therms")
    mcf_c = col("mcf", "gas_mcf")
    bk = sum(float(r[kwh_c]) for r in rows) if kwh_c else 0.0
    if therm_c:
        bt = sum(float(r[therm_c]) for r in rows)
    elif mcf_c:
        bt = sum(float(r[mcf_c]) * therms_per_mcf for r in rows)
    else:
        raise ValueError("bills CSV needs therms or mcf column")
    if not kwh_c:
        raise ValueError("bills CSV needs kwh column")
    return bk, bt


def score_monthly_run(
    eplusout_csv: Path,
    bills_csv: Path,
    *,
    area_ft2: float,
    run_id: str | None = None,
    property_type: str = "office",
    therms_per_mcf: float = MCF_TO_THERM,
) -> dict[str, Any]:
    """Compare last-12 monthly facility meters to bills; area_scale stamped 1.0."""
    bk, bt = _bill_totals(bills_csv, therms_per_mcf=therms_per_mcf)
    bill_eui = (bk * KWH_TO_KBTU + bt * THERM_TO_KBTU) / float(area_ft2)

    df = pd.read_csv(eplusout_csv)
    elec_c = next(
        (c for c in df.columns if "Electricity:Facility" in c and "Monthly" in c),
        None,
    )
    gas_c = next(
        (c for c in df.columns if "NaturalGas:Facility" in c and "Monthly" in c),
        None,
    )
    if elec_c is None or gas_c is None:
        raise ValueError(
            "eplusout.csv missing Electricity:Facility / NaturalGas:Facility Monthly columns "
            "(add Output:Meter,…,Monthly in the IDF)"
        )
    e = float(last12_monthly(df[elec_c]).sum()) * J_TO_KWH
    g = float(last12_monthly(df[gas_c]).sum()) * J_TO_THERM
    eui = (e * KWH_TO_KBTU + g * THERM_TO_KBTU) / float(area_ft2)

    out: dict[str, Any] = {
        "run_id": run_id or Path(eplusout_csv).parent.name,
        "area_scale": 1.0,
        "area_ft2": float(area_ft2),
        "model_kwh": round(e, 1),
        "model_therms": round(g, 1),
        "model_site_eui": round(eui, 1),
        "bill_kwh": round(bk, 1),
        "bill_therms": round(bt, 1),
        "bill_site_eui": round(bill_eui, 1),
        "elec_delta_pct": round((e - bk) / bk * 100, 1) if bk else None,
        "gas_delta_pct": round((g - bt) / bt * 100, 1) if bt else None,
        "eui_delta_pct": round((eui - bill_eui) / bill_eui * 100, 1) if bill_eui else None,
        "fuel_mix_score": round(abs((e - bk) / bk) + abs((g - bt) / bt), 3)
        if bk and bt
        else None,
        "note": "Last-12 positive Monthly meters; sizing-period rows skipped. area_scale=1.",
    }
    try:
        from wattlab.benchmarks import compare_eui

        out["model_peer"] = compare_eui(eui, property_type)
    except Exception as exc:  # pragma: no cover
        out["model_peer_error"] = str(exc)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab score-monthly",
        description="Score eplusout Monthly meters vs bills (last 12 mo, area_scale=1).",
    )
    p.add_argument("eplusout_csv")
    p.add_argument("--bills", required=True)
    p.add_argument("--area-ft2", type=float, required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--property-type", default="office")
    p.add_argument("--therms-per-mcf", type=float, default=MCF_TO_THERM)
    p.add_argument("--out", default=None, help="Write JSON scorecard")
    args = p.parse_args(argv)
    sc = score_monthly_run(
        Path(args.eplusout_csv),
        Path(args.bills),
        area_ft2=args.area_ft2,
        run_id=args.run_id,
        property_type=args.property_type,
        therms_per_mcf=args.therms_per_mcf,
    )
    text = json.dumps(sc, indent=2) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
