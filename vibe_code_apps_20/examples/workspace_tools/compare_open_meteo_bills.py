#!/usr/bin/env python3
import csv, json
from pathlib import Path
import pandas as pd
from wattlab.calibrate import nmbe_cvrmse

J_TO_KWH = 1 / 3.6e6
J_TO_THERM = 1 / 1.05506e8
KWH_TO_KBTU = 3.412
THERM_TO_KBTU = 100.0
AREA = 140000.0

bills = list(csv.DictReader(open("/data/reports/utility_bills_b100_area_weighted.csv")))
bill_by = {r["month"]: (float(r["kwh"]), float(r["therms"])) for r in bills}
df = pd.read_csv("/data/runs/geo_b100_6fl_dial_r4/eplusout.csv")
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
rows = []
obs_k, obs_t, sk, st = [], [], [], []
print(f"{'month':8} {'bill_kWh':>10} {'sim_kWh':>10} {'eΔ%':>7} {'bill_th':>9} {'sim_th':>9} {'gΔ%':>7}")
for bm, mm in order:
    bk, bt = bill_by[bm]
    ek, et = sim[mm]
    ed = (ek - bk) / bk * 100
    gd = (et - bt) / bt * 100
    print(f"{bm:8} {bk:10.0f} {ek:10.0f} {ed:+7.1f} {bt:9.0f} {et:9.0f} {gd:+7.1f}")
    rows.append(
        {
            "month": bm,
            "bill_kwh": bk,
            "sim_kwh": round(ek, 1),
            "elec_delta_pct": round(ed, 1),
            "bill_therms": bt,
            "sim_therms": round(et, 1),
            "gas_delta_pct": round(gd, 1),
        }
    )
    obs_k.append(bk)
    obs_t.append(bt)
    sk.append(ek)
    st.append(et)

elec_g14 = nmbe_cvrmse(obs_k, sk)
gas_g14 = nmbe_cvrmse(obs_t, st)
ann_e, ann_g = sum(sk), sum(st)
ann_be, ann_bg = sum(obs_k), sum(obs_t)
eui = (ann_e * KWH_TO_KBTU + ann_g * THERM_TO_KBTU) / AREA
beui = (ann_be * KWH_TO_KBTU + ann_bg * THERM_TO_KBTU) / AREA
out = {
    "weather": "Open-Meteo AMY (weather_observed → amy.epw), hours Dec2024–Nov2025",
    "run_id": "geo_b100_6fl_dial_r4",
    "amywin_attempt": "geo_b100_6fl_dial_r4_amywin Fatal (zone temp out of bounds on cross-year RunPeriod)",
    "annual": {
        "sim_kwh": round(ann_e, 1),
        "bill_kwh": ann_be,
        "elec_delta_pct": round((ann_e - ann_be) / ann_be * 100, 1),
        "sim_therms": round(ann_g, 1),
        "bill_therms": ann_bg,
        "gas_delta_pct": round((ann_g - ann_bg) / ann_bg * 100, 1),
        "sim_eui": round(eui, 1),
        "bill_eui": round(beui, 1),
    },
    "g14_monthly": {
        "elec": elec_g14,
        "gas": gas_g14,
        "limits": {"nmbe_pct": 5.0, "cvrmse_pct": 15.0},
        "elec_pass": abs(elec_g14["nmbe_pct"]) <= 5 and elec_g14["cvrmse_pct"] <= 15,
        "gas_pass": abs(gas_g14["nmbe_pct"]) <= 5 and gas_g14["cvrmse_pct"] <= 15,
    },
    "monthly": rows,
}
Path("/data/.artifacts/geo_b100_6fl_glass/open_meteo_vs_bills.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print("\nG14 elec", elec_g14, "PASS", out["g14_monthly"]["elec_pass"])
print("G14 gas ", gas_g14, "PASS", out["g14_monthly"]["gas_pass"])
print("annual", out["annual"])
