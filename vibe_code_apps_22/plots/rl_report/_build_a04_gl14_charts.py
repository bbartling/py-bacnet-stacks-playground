"""One-shot: A04 frozen-baseline GL14 charts from the champion sim + utility bills."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SITE = Path(os.environ["SITE_ROOT"]) if os.environ.get("SITE_ROOT") else None
if SITE is None:
    raise SystemExit("set SITE_ROOT to the site pack; machine-local defaults are not allowed")
SIM = (
    SITE
    / "eplus/campaigns/w2a_sc02_aug_in_session_20260809T134542Z"
    / "trials/A04_r02_sum040_clg48_augSchool/sim/eplusmtr.csv"
)
OUT = Path(__file__).resolve().parent
PLOT = OUT / "plots"


def month_from_stamp(stamp: str) -> str:
    mm = int(re.match(r"^(\d{1,2})/", str(stamp).strip()).group(1))
    year = "2025" if mm >= 8 else "2026"
    return f"{year}-{mm:02d}"


def load_bills() -> pd.DataFrame:
    for cand in [
        SITE / "utilities/electricity_utility.csv",
        SITE / "utilities/electricity.csv",
    ]:
        df = pd.read_csv(cand)
        cols = {c.strip().lower(): c for c in df.columns}
        month_c = next((cols[k] for k in cols if "month" in k), None)
        kwh_c = next(
            (cols[k] for k in cols if k in ("kwh", "kwh total", "kwh_obs") or "kwh" in k),
            None,
        )
        if month_c and kwh_c:
            out = df[[month_c, kwh_c]].copy()
            out.columns = ["month", "kwh_obs"]
            out["kwh_obs"] = (
                out["kwh_obs"].astype(str).str.replace(",", "", regex=False).astype(float)
            )
            out["month"] = out["month"].astype(str).str.slice(0, 7)
            return out
    raise SystemExit("no bills")


def main() -> None:
    PLOT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SIM)
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    elec_m = next(c for c in df.columns if "Electricity:Facility" in c and "Monthly" in c)
    elec_h = next(c for c in df.columns if "Electricity:Facility" in c and "Hourly" in c)

    rows = []
    for _, r in df.iterrows():
        val = r.get(elec_m)
        if pd.isna(val) or float(val) == 0:
            continue
        stamp = str(r[date_col])
        if "24:00" not in stamp and not re.search(r"/(28|29|30|31)\s", stamp):
            continue
        rows.append((month_from_stamp(stamp), float(val) / 3_600_000.0))
    mdf = pd.DataFrame(rows, columns=["month", "kwh_sim"]).groupby("month", as_index=False).last()
    bills = load_bills()
    m = bills.merge(mdf, on="month", how="inner").sort_values("month")
    m["pct"] = 100.0 * (m["kwh_sim"] - m["kwh_obs"]) / m["kwh_obs"]
    obs = m.kwh_obs.to_numpy(float)
    simv = m.kwh_sim.to_numpy(float)
    n = len(obs)
    mean = float(obs.mean())
    dof = n - 1
    nmbe = 100.0 * float(np.sum(obs - simv)) / (dof * mean)
    cv = 100.0 * float(np.sqrt(np.sum((obs - simv) ** 2) / dof)) / mean

    hdf = df.loc[df[elec_h].notna(), [date_col, elec_h]].copy()
    hdf["kw"] = hdf[elec_h].astype(float) / 3_600_000.0
    hdf["month"] = hdf[date_col].map(month_from_stamp)
    gl14_months = set(m.month)
    hdf = hdf[hdf["month"].isin(gl14_months)]

    iv = pd.read_csv(SITE / "utilities/demand_interval_kw.csv")
    iv["ts"] = pd.to_datetime(iv.timestamp_utc, utc=True)
    ivh = iv.set_index("ts").kw_demand.resample("h").mean().dropna()
    # Align duration window to the same 10 billed months (America/Chicago).
    local = ivh.index.tz_convert("America/Chicago")
    month_key = pd.Series(local.strftime("%Y-%m"), index=ivh.index)
    ivh = ivh[month_key.isin(gl14_months)]

    def duration_kw(kw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ordered = np.sort(np.asarray(kw, float))[::-1]
        xs = np.linspace(0, 100, 101)
        ys = np.interp(xs / 100.0 * (len(ordered) - 1), np.arange(len(ordered)), ordered)
        return xs, ys

    xs_a, ys_a = duration_kw(ivh.values)
    xs_s, ys_s = duration_kw(hdf.kw.values)

    edges = np.arange(0, 361, 20)
    hist_a, _ = np.histogram(ivh.values, bins=edges)
    hist_s, _ = np.histogram(hdf.kw.values, bins=edges)
    pct_a = 100.0 * hist_a / hist_a.sum()
    pct_s = 100.0 * hist_s / hist_s.sum()
    labels = [f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(edges) - 1)]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.axhline(0, color="#888", lw=1)
    ax.axhline(5, color="#c45c26", ls="--", lw=1, label="±5% NMBE gate (not a per-month cap)")
    ax.axhline(-5, color="#c45c26", ls="--", lw=1)
    cats = [s[2:] for s in m.month]
    ax.plot(cats, m.pct, marker="o", color="#1f4e79", label="(A04 − bill) / bill")
    ax.set_ylabel("Monthly difference (%)")
    ax.set_xlabel("Bill month")
    ax.set_title("A04 frozen baseline vs utility bills — monthly % difference")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT / "a04_gl14_monthly_pct.png", dpi=140)
    plt.close()

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(xs_a, ys_a, color="#333", label="CS interval meter (hourly mean kW)")
    ax.plot(xs_s, ys_s, color="#1f4e79", label="A04 Electricity:Facility (hourly kW)")
    ax.set_xlabel("% of hours (highest load at 0%)")
    ax.set_ylabel("kW")
    ax.set_title("Load-duration: A04 frozen schedules vs actual interval meter")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT / "a04_gl14_load_duration.png", dpi=140)
    plt.close()

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    w = 0.4
    ax.bar(x - w / 2, pct_a, width=w, color="#555", label="% of actual hours")
    ax.bar(x + w / 2, pct_s, width=w, color="#1f4e79", label="% of A04 hours")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("% of hours")
    ax.set_xlabel("Hourly kW bin")
    ax.set_title("Share of hours by load bin — actual vs A04 (shape check, not GL14)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(PLOT / "a04_gl14_load_bin_share.png", dpi=140)
    plt.close()

    payload = {
        "nmbe_pct": round(float(nmbe), 3),
        "cvrmse_pct": round(float(cv), 3),
        "n_months": int(n),
        "scorecard_nmbe": 0.984,
        "scorecard_cvrmse": 10.447,
        "jan26_peak_kw": 287.5,
        "months": list(m.month),
        "month_labels": cats,
        "kwh_obs": [round(float(x), 1) for x in m.kwh_obs],
        "kwh_sim": [round(float(x), 1) for x in m.kwh_sim],
        "pct_diff": [round(float(x), 2) for x in m.pct],
        "duration_pct_hours": list(range(0, 101, 5)),
        "duration_kw_actual": [round(float(ys_a[i]), 1) for i in range(0, 101, 5)],
        "duration_kw_a04": [round(float(ys_s[i]), 1) for i in range(0, 101, 5)],
        "bin_labels": labels,
        "bin_pct_actual": [round(float(x), 2) for x in pct_a],
        "bin_pct_a04": [round(float(x), 2) for x in pct_s],
        "kw_mean_actual": round(float(ivh.mean()), 1),
        "kw_mean_a04": round(float(hdf.kw.mean()), 1),
        "kw_max_actual": round(float(ivh.max()), 1),
        "kw_max_a04": round(float(hdf.kw.max()), 1),
        "source_sim": str(SIM),
        "source_bills": "utilities/electricity_utility.csv billed kWh",
        "source_interval": "utilities/demand_interval_kw.csv hourly-mean",
    }
    (OUT / "a04_gl14_payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("nmbe_pct", "cvrmse_pct", "n_months", "pct_diff")}, indent=2))


if __name__ == "__main__":
    main()
