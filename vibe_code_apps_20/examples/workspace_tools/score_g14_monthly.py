#!/usr/bin/env python3
"""Monthly G14 score for elec+gas vs B100 bills (Open-Meteo month align)."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd
from wattlab.calibrate import nmbe_cvrmse

J_TO_KWH = 1 / 3.6e6
J_TO_THERM = 1 / 1.05506e8


def score(eplusout: Path, bills: Path) -> dict:
    bill_rows = list(csv.DictReader(open(bills)))
    bill_by = {r["month"]: (float(r["kwh"]), float(r["therms"])) for r in bill_rows}
    df = pd.read_csv(eplusout)
    sub = df[
        [
            "Date/Time",
            "Electricity:Facility [J](Monthly)",
            "NaturalGas:Facility [J](Monthly)",
        ]
    ].dropna(subset=["Electricity:Facility [J](Monthly)"])
    sub = sub[sub["Electricity:Facility [J](Monthly)"] > 0].iloc[-12:]
    sim = {}
    for _, row in sub.iterrows():
        mm = str(row["Date/Time"]).strip()[:2]
        sim[mm] = (
            float(row["Electricity:Facility [J](Monthly)"]) * J_TO_KWH,
            float(row["NaturalGas:Facility [J](Monthly)"]) * J_TO_THERM,
        )
    order = [
        ("2024-12", "12"),
        ("2025-01", "01"),
        ("2025-02", "02"),
        ("2025-03", "03"),
        ("2025-04", "04"),
        ("2025-05", "05"),
        ("2025-06", "06"),
        ("2025-07", "07"),
        ("2025-08", "08"),
        ("2025-09", "09"),
        ("2025-10", "10"),
        ("2025-11", "11"),
    ]
    obs_k, obs_t, sk, st = [], [], [], []
    monthly = []
    for bm, mm in order:
        bk, bt = bill_by[bm]
        ek, et = sim[mm]
        monthly.append(
            {
                "month": bm,
                "elec_delta_pct": round((ek - bk) / bk * 100, 1),
                "gas_delta_pct": round((et - bt) / bt * 100, 1),
                "sim_therms": round(et, 1),
                "bill_therms": bt,
            }
        )
        obs_k.append(bk)
        obs_t.append(bt)
        sk.append(ek)
        st.append(et)
    elec = nmbe_cvrmse(obs_k, sk)
    gas = nmbe_cvrmse(obs_t, st)
    return {
        "elec": elec,
        "gas": gas,
        "elec_pass": abs(elec["nmbe_pct"]) <= 5 and elec["cvrmse_pct"] <= 15,
        "gas_pass": abs(gas["nmbe_pct"]) <= 5 and gas["cvrmse_pct"] <= 15,
        "g14_pass": False,  # filled below
        "annual_elec_delta_pct": round((sum(sk) - sum(obs_k)) / sum(obs_k) * 100, 1),
        "annual_gas_delta_pct": round((sum(st) - sum(obs_t)) / sum(obs_t) * 100, 1),
        "monthly": monthly,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("eplusout")
    ap.add_argument("--bills", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    out = score(Path(args.eplusout), Path(args.bills))
    out["g14_pass"] = out["elec_pass"] and out["gas_pass"]
    print(json.dumps(out, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
