#!/usr/bin/env python3
"""Publish a hash-bearing end-use/scope audit for a B59 screening run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from vibe23.b59_campaign_runner import parse_hourly_meter
from vibe23.b59_model import (
    METER_LIGHTING_NORTH_UNMETERED,
    METER_LIGHTING_SOUTH,
    METER_MELS,
    METER_MODEL_HVAC,
    METER_PARTIAL_TARGET_PROXY,
    METER_TERMINAL_HEAT_UNRESOLVED,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _simulated_kwh(path: Path, meter: str) -> float:
    return float(parse_hourly_meter(path, meter).sum() / 3_600_000.0)


def build_scope_audit(eplus_csv: Path, measured_monthly: Path, output_dir: Path) -> dict:
    measured = pd.read_csv(measured_monthly)
    measured_totals = {
        "meter_bound_mels": float(measured["mels_bound_kwh"].sum()),
        "meter_bound_south_lighting": float(measured["lighting_bound_kwh"].sum()),
        "hvac_panels_scope_gap": float(measured["hvac_panels_bound_kwh"].sum()),
        "derived_office_subtotal": float(measured["energy_kwh"].sum()),
    }
    definitions = [
        ("meter_bound_mels", METER_MELS, "matched only by provisional model load category"),
        ("meter_bound_south_lighting", METER_LIGHTING_SOUTH, "north lighting absent from telemetry"),
        ("hvac_panels_scope_gap", METER_MODEL_HVAC, "panels include unresolved elevator/plant loads"),
        ("derived_office_subtotal", METER_PARTIAL_TARGET_PROXY, "aggregate screening proxy only"),
        ("unmetered_north_lighting", METER_LIGHTING_NORTH_UNMETERED, "no measured lig_N channel"),
        ("unresolved_terminal_reheat", METER_TERMINAL_HEAT_UNRESOLVED, "proxy is not documented hydronic UFT plant"),
        ("facility_total_not_comparable", "Electricity:Facility", "must never be scored against office subtotal"),
    ]
    rows = []
    for category, meter, caveat in definitions:
        measured_kwh = measured_totals.get(category)
        simulated_kwh = _simulated_kwh(eplus_csv, meter)
        error_pct = None if measured_kwh is None else 100.0 * (simulated_kwh - measured_kwh) / measured_kwh
        rows.append(
            {
                "category": category,
                "measured_kwh": measured_kwh,
                "simulated_kwh": simulated_kwh,
                "sim_minus_measured_pct": error_pct,
                "model_meter": meter,
                "disposition": caveat,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    table_path = output_dir / "champion_end_use_scope_audit.csv"
    pd.DataFrame(rows).to_csv(table_path, index=False)
    matched = [row for row in rows if row["measured_kwh"] is not None]
    manifest = {
        "schema": "vibe23.b59_champion_scope_audit.v1",
        "claim_status": "SCREENING_ONLY_COMPENSATING_ERROR_DETECTED",
        "sources": {
            "energyplus_csv": {"sha256": _sha256(eplus_csv), "hourly_rows": 8784},
            "measured_monthly": {"name": measured_monthly.name, "sha256": _sha256(measured_monthly)},
        },
        "output": {"name": table_path.name, "sha256": _sha256(table_path), "rows": len(rows)},
        "matched_category_errors_pct": {
            row["category"]: row["sim_minus_measured_pct"] for row in matched
        },
        "conclusion": (
            "The close annual subtotal is produced by large offsetting end-use errors. "
            "It is not evidence of a physically calibrated model."
        ),
    }
    manifest_path = output_dir / "champion_end_use_scope_audit_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eplus-csv", type=Path, required=True)
    parser.add_argument("--measured-monthly", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_scope_audit(args.eplus_csv, args.measured_monthly, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
