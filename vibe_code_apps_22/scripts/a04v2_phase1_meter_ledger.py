"""Phase 1: utility vs BAS meter source ledger (no silent rescaling)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
SITE = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    util_demand = SITE / "utilities" / "electricity_utility_demand.csv"
    util_bills = SITE / "utilities" / "utility_bills_raw.csv"
    interval = SITE / "utilities" / "demand_interval_kw.csv"
    bas = SITE / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    out = _APP / "docs" / "audits" / "figures" / "a04v2" / "phase1"
    out.mkdir(parents=True, exist_ok=True)

    ud = pd.read_csv(util_demand)
    jan = ud[ud["month"].astype(str).str.startswith("2026-01")].iloc[0]
    iv = pd.read_csv(interval)
    iv["timestamp_utc"] = pd.to_datetime(iv["timestamp_utc"], utc=True)
    jan_iv = iv[(iv["timestamp_utc"] >= "2026-01-01") & (iv["timestamp_utc"] < "2026-02-01")]
    bas_df = pd.read_parquet(bas)
    # interval vs BAS facility_kw correlation sample
    ledger = {
        "schema": "vibe22.a04v2.meter_source_ledger.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "A_utility_provider": {
                "files": [
                    {"path": str(util_demand), "sha256": sha256_file(util_demand)},
                    {"path": str(util_bills), "sha256": sha256_file(util_bills) if util_bills.is_file() else None},
                ],
                "use_for": ["monthly_billed_energy_kwh", "monthly_billed_demand_kw", "tariff_context"],
                "january_2026_billed_demand_kw": float(jan["billed_demand_kw"]),
                "january_2026_kwh": float(jan["kwh"]),
                "not_for": ["15min_load_shape", "morning_recovery_timing"],
            },
            "B_bas_bacnet_electrical_submeter": {
                "files": [
                    {
                        "path": str(interval),
                        "sha256": sha256_file(interval),
                        "note": (
                            "Same series family as BAS/BACnet CS_ELEC_METER. "
                            "NOT an independent utility AMI source. Do not label as utility-provider interval data."
                        ),
                    },
                    {"path": str(bas), "sha256": sha256_file(bas)},
                ],
                "use_for": [
                    "5min_15min_30min_hourly_load_shape",
                    "peak_timing",
                    "morning_recovery",
                    "weekday_weekend_patterns",
                    "zone_temperature_transients",
                ],
                "january_2026_interval_max_kw": float(jan_iv["kw_demand"].max()) if len(jan_iv) else None,
                "january_2026_15min_mean_peak_note": "BAS 15-min mean peak historically ~304 kW; verify on this build",
                "observed_context": {
                    "bas_5min_peak_kw_approx": 330.0,
                    "bas_15min_mean_peak_kw_approx": 304.0,
                    "bas_30min_mean_peak_kw_approx": 288.0,
                    "utility_jan2026_billed_demand_kw": 284.82,
                },
            },
        },
        "open_questions": [
            "Meter boundary: does CS_ELEC_METER include loads absent from A04 IdealLoads/W2A plant?",
            "Timestamp convention of demand_interval_kw.csv (interval end vs start)",
            "DST handling between BAS local and UTC",
            "Consistent bias between monthly integrated BAS kWh and utility billed kWh",
        ],
        "correction_policy": (
            "Do not rescale BAS merely to improve validation. Any correction needs physical/metering basis, "
            "estimated on development data only, checked on held-out validation."
        ),
        "january_2026_utility_vs_interval": {
            "utility_billed_demand_kw": float(jan["billed_demand_kw"]),
            "interval_max_kw": float(jan_iv["kw_demand"].max()) if len(jan_iv) else None,
            "interval_rows": int(len(jan_iv)),
            "interpretation": (
                "Interval max exceeds billed demand; billed demand uses a utility averaging window "
                "(document before peak-tolerance freeze)."
            ),
        },
        "real_baseline_15min": {
            "n_rows": int(len(bas_df)),
            "columns_present": sorted(set(bas_df.columns) & {
                "facility_kw", "zone_temp_1F_A_f", "zone_temp_1F_B_f", "zone_temp_1F_C_f",
                "zone_temp_1F_D_f", "zone_temp_2F_A_f", "zone_temp_2F_B_f", "oat_f",
            }),
        },
    }
    # monthly BAS vs utility kWh if possible
    if "timestamp_local" in bas_df.columns and "facility_kw" in bas_df.columns:
        t = pd.to_datetime(bas_df["timestamp_local"])
        bas_df = bas_df.copy()
        bas_df["_month"] = t.dt.strftime("%Y-%m")
        # 15-min kWh = kw * 0.25
        monthly = bas_df.groupby("_month")["facility_kw"].sum() * 0.25
        util_map = {str(r["month"]): float(r["kwh"]) for _, r in ud.iterrows()}
        cmp_rows = []
        for m, kwh in monthly.items():
            if m in util_map:
                cmp_rows.append({
                    "month": m,
                    "bas_integrated_kwh": float(kwh),
                    "utility_billed_kwh": util_map[m],
                    "delta_kwh": float(kwh - util_map[m]),
                    "pct_diff": float(100.0 * (kwh - util_map[m]) / util_map[m]) if util_map[m] else None,
                })
        ledger["monthly_bas_vs_utility_kwh"] = cmp_rows
        pd.DataFrame(cmp_rows).to_csv(out / "monthly_bas_vs_utility_kwh.csv", index=False)

    (out / "meter_source_ledger.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    md = out / "meter_source_ledger.md"
    md.write_text(
        "# Meter source ledger (Phase 1)\n\n"
        "**A — Utility provider:** monthly billed energy/demand. Jan 2026 billed demand "
        f"**{jan['billed_demand_kw']} kW**.\n\n"
        "**B — BAS/BACnet submeter:** `utilities/demand_interval_kw.csv` is the same series family as "
        "`CS_ELEC_METER`, **not** independent utility AMI. Use for load shape and timing only.\n\n"
        "Do not rescale BAS to force validation.\n",
        encoding="utf-8",
    )
    print(json.dumps({k: ledger[k] for k in ("schema", "january_2026_utility_vs_interval")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
