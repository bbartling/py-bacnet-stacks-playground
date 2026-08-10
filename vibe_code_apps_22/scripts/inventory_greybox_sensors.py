#!/usr/bin/env python
"""Inventory candidate sensors for a 6-zone grey-box model — never invent points.

Scans LAKESIDE_SITE_ROOT for the live real 15-min store, FDD lookup, master_long,
and weather exports. Missing points are recorded as UNKNOWN / NOT_IN_SITE_EXPORT.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "ml")]

REQUIRED = [
    "facility_kw",
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
    "htg_setpoint",
    "occupancy",
    "hp_enable_or_stage",
    "fan_status",
    "sat_rat",
    "loop_ewt",
    "loop_lwt",
    "pump_speed_or_kw",
    "oat_f",
    "rh_pct",
    "solar_ghi",
    "doas_or_oa_signal",
]

# Plant / setpoint points — never invent BACnet object IDs
_PLANT_POINTS = {
    "hp_enable_or_stage",
    "fan_status",
    "sat_rat",
    "loop_ewt",
    "loop_lwt",
    "pump_speed_or_kw",
    "doas_or_oa_signal",
    "htg_setpoint",
}


def _site() -> Path:
    for k in ("LAKESIDE_SITE_ROOT", "VIBE22_SITE_ROOT"):
        v = os.environ.get(k, "").strip()
        if v and Path(v).is_dir():
            return Path(v)
    return Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def _columns_from_parquet(p: Path) -> set[str]:
    try:
        import pandas as pd

        return set(map(str, pd.read_parquet(p, columns=None).columns))
    except Exception:
        return set()


def _scan_paths(site: Path) -> tuple[set[str], list[str]]:
    found_cols: set[str] = set()
    sources: list[str] = []
    candidates = [
        site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet",
        site / "ml" / "artifacts" / "real_15min_store.parquet",
        site / "reports" / "master_long.parquet",
        site / "clean_data" / "weather" / "history_wide.csv",
        site / "fdd_device_lookup.csv",
        _APP / "ml" / "artifacts" / "fixtures",
    ]
    for p in candidates:
        if p.is_dir():
            for q in p.glob("*.parquet"):
                found_cols |= _columns_from_parquet(q)
                sources.append(str(q))
            continue
        if not p.is_file():
            continue
        sources.append(str(p))
        if p.suffix == ".parquet":
            found_cols |= _columns_from_parquet(p)
        elif p.suffix == ".csv":
            try:
                import pandas as pd

                found_cols |= set(map(str, pd.read_csv(p, nrows=2).columns))
            except Exception:
                pass
    # schema JSON next to real store (column list without loading full parquet twice)
    schema = site / "ml" / "artifacts" / "real_baseline_15min_v1_schema.json"
    if schema.is_file():
        try:
            import json

            raw = json.loads(schema.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cols = raw.get("columns") or raw.get("fields") or []
                if isinstance(cols, list):
                    found_cols |= {str(c) for c in cols}
                    sources.append(str(schema))
        except Exception:
            pass
    return found_cols, sources


def inventory(site: Path) -> list[dict[str, str]]:
    found_cols, sources = _scan_paths(site)

    fdd = site / "fdd_device_lookup.csv"
    fdd_note = str(fdd) if fdd.is_file() else "NOT_IN_SITE_EXPORT"

    aliases = {
        "facility_kw": {"facility_kw", "kw", "demand_kw", "site_kw"},
        "zone_temp_1F_A_f": {"zone_temp_1F_A_f", "1F_Area_A", "zn_t_1f_a"},
        "zone_temp_1F_B_f": {"zone_temp_1F_B_f", "1F_Area_B"},
        "zone_temp_1F_C_f": {"zone_temp_1F_C_f", "1F_Area_C"},
        "zone_temp_1F_D_f": {"zone_temp_1F_D_f", "1F_Area_D"},
        "zone_temp_2F_A_f": {"zone_temp_2F_A_f", "2F_Area_A"},
        "zone_temp_2F_B_f": {"zone_temp_2F_B_f", "2F_Area_B"},
        "oat_f": {"oat_f", "oa_t", "outdoor_temp_f"},
        "rh_pct": {"rh_pct", "rh", "relative_humidity"},
        "solar_ghi": {"ghi", "solar", "global_horizontal", "solar_ghi"},
        "occupancy": {"occupied", "occ_frac", "occupancy"},
    }

    rows = []
    low = {c.lower(): c for c in found_cols}
    for req in REQUIRED:
        status = "NOT_IN_SITE_EXPORT"
        identity = "UNKNOWN"
        sample = "UNKNOWN"
        miss = "UNKNOWN"
        stuck = "UNKNOWN"
        usable = "UNKNOWN"
        if req in aliases:
            for a in aliases[req]:
                if a.lower() in low or a in found_cols:
                    status = "PRESENT_IN_EXPORT"
                    identity = low.get(a.lower(), a)
                    sample = "15min_or_source_export"
                    miss = "NOT_COMPUTED"
                    stuck = "NOT_COMPUTED"
                    usable = "PARTIAL — column present; quality not scored in this inventory"
                    break
        if req in _PLANT_POINTS and status != "PRESENT_IN_EXPORT":
            status = "NOT_IN_SITE_EXPORT"
            identity = "UNKNOWN — do not invent BACnet object-id"
        rows.append(
            {
                "point": req,
                "status": status,
                "bacnet_or_column_identity": identity,
                "sampling_period": sample,
                "missing_fraction": miss,
                "stuck_fraction": stuck,
                "range": "UNKNOWN",
                "timestamp_quality": "UNKNOWN",
                "usable_date_span": usable,
                "fdd_lookup": fdd_note,
                "sources_scanned": ";".join(sources) if sources else "NONE",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_md(path: Path, rows: list[dict[str, str]], site: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_ok = sum(1 for r in rows if r["status"] == "PRESENT_IN_EXPORT")
    lines = [
        "# Grey-box sensor manifest (Lakeside)",
        "",
        f"**Site scanned:** `{site}`",
        f"**Present:** {n_ok}/{len(rows)}",
        "",
        "Honesty: missing points are **UNKNOWN / NOT_IN_SITE_EXPORT**. "
        "No BACnet object IDs were invented. Identities for PRESENT rows are "
        "**parquet/CSV column names** from the real 15-min store (not BACnet objects).",
        "",
        "| Point | Status | Identity |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['point']}` | {r['status']} | {r['bacnet_or_column_identity']} |"
        )
    lines.append("")
    lines.append("See also `reports/ml/greybox_sensor_manifest.csv` (local / gitignored OK).")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, default=None)
    ap.add_argument(
        "--csv-out",
        type=Path,
        default=_APP / "reports" / "ml" / "greybox_sensor_manifest.csv",
    )
    ap.add_argument(
        "--md-out",
        type=Path,
        default=_APP / "docs" / "audits" / "greybox_sensor_manifest.md",
    )
    args = ap.parse_args(argv)
    site = args.site or _site()
    rows = inventory(site)
    write_csv(args.csv_out, rows)
    write_md(args.md_out, rows, site)
    n_ok = sum(1 for r in rows if r["status"] == "PRESENT_IN_EXPORT")
    print(f"wrote {args.csv_out} and {args.md_out} present={n_ok}/{len(rows)} site={site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
