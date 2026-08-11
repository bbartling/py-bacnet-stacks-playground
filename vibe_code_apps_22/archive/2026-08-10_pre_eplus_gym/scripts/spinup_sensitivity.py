#!/usr/bin/env python
"""Spin-up / pre-roll sensitivity for DSM farm thermal history.

Writes reports/eplus/spinup_sensitivity.csv.
Use --from-farm-root to fill metrics from existing timestep parquets when available.
Short pre-roll is insufficient for GLHE seasonal ground claims.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "scripts"), str(_APP / "ml")]

PRE_ROLLS = (0, 3, 7, 14)
OUT_DEFAULT = _APP / "reports" / "eplus" / "spinup_sensitivity.csv"


def dry_rows(eval_day: str = "2026-01-26") -> list[dict]:
    rows = []
    for pre in PRE_ROLLS:
        rows.append(
            {
                "eval_day": eval_day,
                "pre_roll_days": pre,
                "daily_kwh": "",
                "peak_kw": "",
                "peak_step": "",
                "zone_mae_vs_pr7": "",
                "ewt_mean": "",
                "note": (
                    "SCAFFOLD — run eplus_heating_dsm_farm.py --pre-roll-days "
                    f"{pre} offline; GLHE seasonal history NOT captured by short pre-roll"
                ),
                "glhe_seasonal_ok": "false",
                "recommendation": "UNRESOLVED",
            }
        )
    return rows


def rows_from_farm_root(farm_root: Path, eval_day: str) -> list[dict]:
    """Best-effort fill from any timestep_proxy_mat.parquet under farm_root."""
    import pandas as pd

    rows = []
    pq = list(farm_root.rglob("timestep_proxy_mat.parquet"))
    if not pq:
        return dry_rows(eval_day)
    # Aggregate whatever exists — pre_roll tag unknown → mark UNKNOWN preroll
    peaks = []
    for p in pq[:20]:
        try:
            df = pd.read_parquet(p)
            if "site_electric_proxy_kw" in df.columns:
                kw = df["site_electric_proxy_kw"].to_numpy(dtype=float)
            elif "facility_kw" in df.columns:
                kw = df["facility_kw"].to_numpy(dtype=float)
            else:
                continue
            peaks.append(float(kw.max()))
        except Exception:
            continue
    for pre in PRE_ROLLS:
        rows.append(
            {
                "eval_day": eval_day,
                "pre_roll_days": pre,
                "daily_kwh": "",
                "peak_kw": (max(peaks) if peaks and pre == 0 else ""),
                "peak_step": "",
                "zone_mae_vs_pr7": "",
                "ewt_mean": "",
                "note": (
                    f"PARTIAL from {farm_root} n_parquets={len(pq)}; "
                    "re-run farm at each --pre-roll-days for true sensitivity"
                ),
                "glhe_seasonal_ok": "false",
                "recommendation": "UNRESOLVED",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--from-farm-root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--eval-day", default="2026-01-26")
    args = ap.parse_args(argv)
    if args.from_farm_root and args.from_farm_root.is_dir():
        rows = rows_from_farm_root(args.from_farm_root, args.eval_day)
    else:
        rows = dry_rows(args.eval_day)
    write_csv(args.out, rows)
    print(f"wrote {args.out} n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
