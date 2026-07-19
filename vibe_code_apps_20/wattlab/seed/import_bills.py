"""Privacy-safe monthly bill import → ``utility_bills.csv`` / answers fragment.

Companion fuel workbooks (xlsx) are never ingested here. Export or normalize to
CSV first, then import. Shared-electric meters require an explicit allocation
method — never silently assumed as measured building truth.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from wattlab.benchmarks.meters import THERMS_PER_MCF, load_bill_csv

ALLOCATION_METHODS = ("area_weighted", "equal", "manual", "none")


def _window_months(start: str, end: str) -> list[str]:
    """Inclusive YYYY-MM window."""
    ys, ms = int(start[:4]), int(start[5:7])
    ye, me = int(end[:4]), int(end[5:7])
    out: list[str] = []
    y, m = ys, ms
    while (y, m) <= (ye, me):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def normalize_monthly_bills(
    *,
    electric_csv: Path | None = None,
    gas_csv: Path | None = None,
    gas_unit: str = "therms",
    window: str | None = None,
    electric_share: float = 1.0,
    allocation_method: str = "none",
    allocation_note: str = "",
) -> dict[str, Any]:
    """Build a monthly bill table keyed by YYYY-MM.

    Returns ``{"rows": [...], "provenance": {...}}``.
    """
    if electric_csv is None and gas_csv is None:
        raise ValueError("Provide --electric and/or --gas CSV path")
    if allocation_method not in ALLOCATION_METHODS:
        raise ValueError(f"allocation must be one of {ALLOCATION_METHODS}")
    if not 0.0 < float(electric_share) <= 1.0:
        raise ValueError("electric_share must be in (0, 1]")

    months: set[str] = set()
    elec_by: dict[str, float] = {}
    gas_by: dict[str, float] = {}

    if electric_csv is not None:
        edf = load_bill_csv(electric_csv)
        for _, r in edf.iterrows():
            m = str(r["month"])[:7]
            elec_by[m] = float(r["usage"]) * float(electric_share)
            months.add(m)
    if gas_csv is not None:
        gdf = load_bill_csv(gas_csv)
        factor = THERMS_PER_MCF if gas_unit.lower() in {"mcf", "ccf"} else 1.0
        if gas_unit.lower() == "ccf":
            factor = THERMS_PER_MCF / 10.0
        for _, r in gdf.iterrows():
            m = str(r["month"])[:7]
            gas_by[m] = float(r["usage"]) * factor
            months.add(m)

    if window:
        if ":" not in window:
            raise ValueError("--window must be YYYY-MM:YYYY-MM")
        start, end = window.split(":", 1)
        allowed = set(_window_months(start.strip(), end.strip()))
        months = {m for m in months if m in allowed}

    rows = []
    for m in sorted(months):
        rows.append(
            {
                "month": m,
                "period": m,
                "kwh": elec_by.get(m),
                "therms": gas_by.get(m),
            }
        )

    provenance = {
        "electric_csv": str(electric_csv) if electric_csv else None,
        "gas_csv": str(gas_csv) if gas_csv else None,
        "gas_unit": gas_unit,
        "window": window,
        "electric_share": float(electric_share),
        "allocation_method": allocation_method,
        "allocation_note": allocation_note
        or (
            "Shared-meter electric share is a scenario, not measured submetered truth."
            if float(electric_share) < 1.0
            else "Whole-meter assignment (share=1.0)."
        ),
        "schema": "wattlab_utility_bills_v1",
        "month_key": "YYYY-MM",
    }
    return {"rows": rows, "provenance": provenance}


def write_utility_bills_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["month", "kwh", "therms"])
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "month": r["month"],
                    "kwh": "" if r.get("kwh") is None else r["kwh"],
                    "therms": "" if r.get("therms") is None else r["therms"],
                }
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab seed import-bills",
        description=(
            "Normalize monthly electric/gas CSVs into utility_bills.csv "
            "(YYYY-MM). Does not read xlsx workbooks."
        ),
    )
    p.add_argument("--electric", type=Path, default=None, help="Monthly electric CSV (kWh)")
    p.add_argument("--gas", type=Path, default=None, help="Monthly gas CSV")
    p.add_argument(
        "--gas-unit",
        default="therms",
        choices=["therms", "mcf", "ccf"],
        help="Gas CSV usage unit (mcf/ccf converted to therms)",
    )
    p.add_argument(
        "--window",
        default=None,
        help="Optional inclusive window YYYY-MM:YYYY-MM",
    )
    p.add_argument(
        "--electric-share",
        type=float,
        default=1.0,
        help="Fraction of shared electric meter assigned to this building (0–1]",
    )
    p.add_argument(
        "--allocation",
        default="none",
        choices=list(ALLOCATION_METHODS),
        help="Documented allocation scenario label (required honesty for shared meters)",
    )
    p.add_argument(
        "--allocation-note",
        default="",
        help="Free-text provenance for how the electric share was chosen",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output utility_bills.csv path",
    )
    p.add_argument(
        "--answers-fragment",
        type=Path,
        default=None,
        help="Optional JSON with utility_bills + provenance for twin --inputs merge",
    )
    args = p.parse_args(argv)

    result = normalize_monthly_bills(
        electric_csv=args.electric,
        gas_csv=args.gas,
        gas_unit=args.gas_unit,
        window=args.window,
        electric_share=args.electric_share,
        allocation_method=args.allocation,
        allocation_note=args.allocation_note,
    )
    write_utility_bills_csv(result["rows"], args.out)
    if args.answers_fragment:
        frag = {
            "utility_bills": result["rows"],
            "utility_bills_provenance": result["provenance"],
        }
        args.answers_fragment.parent.mkdir(parents=True, exist_ok=True)
        args.answers_fragment.write_text(json.dumps(frag, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": len(result["rows"]),
                "out": str(args.out),
                "provenance": result["provenance"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
