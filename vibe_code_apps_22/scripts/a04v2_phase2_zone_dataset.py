"""Phase 2: six-zone BAS temperature dataset + event ledger from real_baseline."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
SITE = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")
ZONE_COLS = [
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
]
GATE_DATES = {"2026-01-25", "2026-01-26", "2026-03-16"}
# Primary aggregation chosen BEFORE model trials
PRIMARY_AGG = "mean_of_valid_sensors_preaggregated_in_real_baseline_v1"


def main() -> int:
    bas_path = SITE / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    map_path = SITE / "clean_data" / "LAKESIDE_ES" / "thermal_zone_model.json"
    out = _APP / "docs" / "audits" / "figures" / "a04v2" / "phase2"
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(bas_path)
    t = pd.to_datetime(df["timestamp_local"])
    work = df.copy()
    work["timestamp_local"] = t
    work["date"] = t.dt.date.astype(str)
    work["dow"] = t.dt.dayofweek
    for c in ZONE_COLS:
        work[f"dT_{c}"] = work[c].astype(float).diff().abs()

    # Event flags (15-min)
    occupied = work["occupied"].astype(bool) if "occupied" in work.columns else pd.Series(False, index=work.index)
    occ_chg = occupied.astype(int).diff().fillna(0)
    work["event_morning_recovery"] = (occ_chg == 1) & (t.dt.hour.between(5, 9))
    work["event_evening_setback"] = (occ_chg == -1) & (t.dt.hour.between(15, 20))
    work["very_cold"] = work["oat_f"].astype(float) < 10.0 if "oat_f" in work.columns else False
    work["mild"] = work["oat_f"].astype(float) > 45.0 if "oat_f" in work.columns else False
    work["weekend"] = work["dow"] >= 5

    # Zone disagreement proxy: cross-zone std of temps at each interval
    zmat = work[ZONE_COLS].astype(float)
    work["zone_cross_std_f"] = zmat.std(axis=1)
    work["zone_cross_range_f"] = zmat.max(axis=1) - zmat.min(axis=1)

    # Publish sample columns (not full parquet — large); write event ledger days
    day_stats = []
    for day, g in work.groupby("date"):
        day_stats.append(
            {
                "date": day,
                "n_intervals": int(len(g)),
                "oat_min_f": float(g["oat_f"].min()) if "oat_f" in g else None,
                "oat_max_f": float(g["oat_f"].max()) if "oat_f" in g else None,
                "facility_peak_kw": float(g["facility_kw"].max()) if "facility_kw" in g else None,
                "max_abs_dT_f": float(g[[f"dT_{c}" for c in ZONE_COLS]].max().max()),
                "p99_9_abs_dT_f": float(
                    np.nanquantile(g[[f"dT_{c}" for c in ZONE_COLS]].to_numpy().reshape(-1), 0.999)
                ),
                "n_morning_recovery": int(g["event_morning_recovery"].sum()),
                "n_evening_setback": int(g["event_evening_setback"].sum()),
                "mean_zone_cross_std_f": float(g["zone_cross_std_f"].mean()),
                "gate_or_smoke_date": day in GATE_DATES,
                "weekend": bool(g["weekend"].iloc[0]),
            }
        )
    days = pd.DataFrame(day_stats).sort_values("date")
    # Chronological event splits for transient validation (exclude gate dates from held-out)
    eligible = days[~days["gate_or_smoke_date"]].copy()
    n = len(eligible)
    # ~70/15/15 chronological on unique days
    i1 = int(0.70 * n)
    i2 = int(0.85 * n)
    eligible["fold"] = "train_dev"
    eligible.iloc[i1:i2, eligible.columns.get_loc("fold")] = "model_selection_val"
    eligible.iloc[i2:, eligible.columns.get_loc("fold")] = "heldout_transient"
    days = days.merge(eligible[["date", "fold"]], on="date", how="left")
    days.loc[days["gate_or_smoke_date"], "fold"] = "gate_smoke_excluded"

    days.to_csv(out / "day_event_ledger.csv", index=False)

    mapping = None
    if map_path.is_file():
        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        (out / "thermal_zone_model_provenance.json").write_text(
            json.dumps(
                {
                    "path": str(map_path),
                    "sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
                    "note": "67 heat pumps → six BAS groups; preserve mapping",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    manifest = {
        "schema": "vibe22.a04v2.phase2_zone_dataset.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_parquet": str(bas_path),
        "source_sha256": hashlib.sha256(bas_path.read_bytes()).hexdigest(),
        "primary_aggregation_method": PRIMARY_AGG,
        "aggregation_justification": (
            "real_baseline_15min_v1 already publishes six BAS-aligned zone columns from the "
            "67-HP thermal_zone_model map. Per-interval sensor min/max/std within each group "
            "are not in this parquet; cross-zone std/range are published as disagreement proxies. "
            "Do not hide disagreement — report zone_cross_std_f / zone_cross_range_f."
        ),
        "zone_cols": ZONE_COLS,
        "gate_smoke_dates_excluded_from_heldout": sorted(GATE_DATES),
        "n_days": int(len(days)),
        "fold_counts": days["fold"].value_counts(dropna=False).to_dict(),
        "january_not_pristine": True,
    }
    (out / "phase2_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fold_counts": manifest["fold_counts"], "n_days": manifest["n_days"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
