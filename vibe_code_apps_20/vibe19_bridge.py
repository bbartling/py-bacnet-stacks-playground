"""Bridge vibe19 agent-export bundles → WattLab evidence + suggested measures.

Reads an OpenFDD vibe19 export directory (export_agent_bundle / agent_afdd.py --out)
and maps fault hours / analytics into pre-approved MeasureBriefs tagged source=vibe19.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ecm_library.measure_sets import load_measure_sets

PRODUCT = "OpenFDD WattLab"

# Mapping: vibe19 rule_id → WattLab measure catalog id
RULE_TO_MEASURE = {
    "SCHED-247": "ECM-AHU-SCHED-ALIGN",
    "SCHED-1": "ECM-AHU-SCHED-ALIGN",
    "AHU-DUCTHI": "ECM-GL36-AIRSIDE",
    "FC1": "ECM-GL36-AIRSIDE",
    "VAV-1": "ECM-GL36-AIRSIDE",
    "MECH-OAT-1": "ECM-CHILLER-LOCKOUT",
    "ECON-3": "ECM-CHILLER-LOCKOUT",
    "ECON-6": "ECM-CHILLER-LOCKOUT",
    "CHW-NOLOAD-1": "ECM-CHILLER-LOCKOUT",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _f(row: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            try:
                return float(row[k])
            except ValueError:
                continue
    return default


def suggest_from_bundle(bundle_dir: Path | str) -> dict[str, Any]:
    """
    Parse a vibe19 agent-export bundle and return evidence + suggested measures.

    Expected files (any subset OK):
      fdd_summary.csv, motor_weekly.csv, economizer_weather.csv, run_report.json
    """
    root = Path(bundle_dir)
    fdd = _read_csv(root / "fdd_summary.csv")
    motor_weekly = _read_csv(root / "motor_weekly.csv")
    econ = _read_csv(root / "economizer_weather.csv")
    run_report: dict[str, Any] = {}
    rr_path = root / "run_report.json"
    if rr_path.is_file():
        run_report = json.loads(rr_path.read_text(encoding="utf-8"))

    catalog = (load_measure_sets().get("catalog") or {})
    evidence: list[dict[str, Any]] = []
    measure_hits: dict[str, dict[str, Any]] = {}

    # --- fdd_summary rows ---
    for row in fdd:
        rule = (row.get("rule_id") or "").strip()
        mid = RULE_TO_MEASURE.get(rule)
        if not mid:
            continue
        fault_hours = _f(row, "fault_hours")
        fault_pct = _f(row, "fault_pct")
        status = (row.get("status") or "").upper()
        applicable = str(row.get("applicable") or "true").lower() in {
            "1",
            "true",
            "yes",
            "y",
        }
        # Suggest when fault present or always-on style findings
        interesting = fault_hours > 0 or status in {"FAULT", "FAIL", "WARN"}
        if not applicable or not interesting:
            continue

        ev_id = f"EV-{rule}-{(row.get('equipment_id') or 'SITE')}"
        evidence.append(
            {
                "evidence_id": ev_id,
                "rule_id": rule,
                "equipment_id": row.get("equipment_id"),
                "equipment_type": row.get("equipment_type"),
                "fault_hours": fault_hours,
                "fault_pct": fault_pct,
                "status": status,
                "notes": row.get("notes") or "",
                "source": "vibe19",
                "maps_to_measure": mid,
            }
        )
        hit = measure_hits.setdefault(
            mid,
            {
                "measure_id": mid,
                "evidence_ids": [],
                "rule_ids": set(),
                "equipment_ids": set(),
                "fault_hours_total": 0.0,
            },
        )
        hit["evidence_ids"].append(ev_id)
        hit["rule_ids"].add(rule)
        if row.get("equipment_id"):
            hit["equipment_ids"].add(row["equipment_id"])
        hit["fault_hours_total"] += fault_hours

    # --- economizer prohibited mech cooling hours → reinforce chiller lockout ---
    prohibited_total = 0.0
    for row in econ:
        prohibited_total += _f(row, "prohibited_mech_hours_below_60f")
    if prohibited_total > 0:
        ev_id = "EV-ECON-PROHIBITED-MECH"
        evidence.append(
            {
                "evidence_id": ev_id,
                "rule_id": "MECH-OAT-1",
                "equipment_id": None,
                "fault_hours": prohibited_total,
                "notes": (
                    f"economizer_weather.csv reports {prohibited_total:.1f}h "
                    "prohibited mechanical cooling below 60°F OAT"
                ),
                "source": "vibe19",
                "maps_to_measure": "ECM-CHILLER-LOCKOUT",
            }
        )
        hit = measure_hits.setdefault(
            "ECM-CHILLER-LOCKOUT",
            {
                "measure_id": "ECM-CHILLER-LOCKOUT",
                "evidence_ids": [],
                "rule_ids": set(),
                "equipment_ids": set(),
                "fault_hours_total": 0.0,
            },
        )
        hit["evidence_ids"].append(ev_id)
        hit["rule_ids"].add("MECH-OAT-1")
        hit["fault_hours_total"] += prohibited_total
        hit["prohibited_mech_hours_below_60f"] = prohibited_total

    # --- motor weekly → occupied-hours hint for schedule measure ---
    schedule_hint: dict[str, Any] | None = None
    if motor_weekly and "ECM-AHU-SCHED-ALIGN" in measure_hits:
        # crude: average hours by weekday label if present
        by_label: dict[str, list[float]] = {}
        for row in motor_weekly:
            lab = row.get("week_label") or row.get("label") or "week"
            by_label.setdefault(lab, []).append(_f(row, "hours"))
        if by_label:
            avgs = {k: sum(v) / len(v) for k, v in by_label.items()}
            schedule_hint = {
                "motor_weekly_avg_hours": {k: round(v, 1) for k, v in avgs.items()},
                "note": "Derived from vibe19 motor_weekly.csv; use to tune occupied start/stop if needed.",
            }

    # --- Build measure list from catalog ---
    measures: list[dict[str, Any]] = []
    for mid, hit in measure_hits.items():
        base = dict(catalog.get(mid) or {"measure_id": mid, "title": mid})
        base = json.loads(json.dumps(base))  # deep copy via JSON
        base["source"] = "vibe19"
        base["review_status"] = "approved"
        base["evidence_ids"] = hit["evidence_ids"]
        base["vibe19_bridge"] = {
            "rule_ids": sorted(hit["rule_ids"]),
            "equipment_ids": sorted(hit["equipment_ids"]),
            "fault_hours_total": round(hit["fault_hours_total"], 1),
            "prohibited_mech_hours_below_60f": hit.get("prohibited_mech_hours_below_60f"),
            "note": "Auto-suggested from vibe19 agent-export bundle",
        }
        if mid == "ECM-AHU-SCHED-ALIGN" and schedule_hint:
            base["schedule_hint"] = schedule_hint
        # Tune chiller lockout from economizer threshold if present
        if mid == "ECM-CHILLER-LOCKOUT":
            patch = base.setdefault("idf_patch", {"name": "chiller_lockout", "params": {}})
            params = patch.setdefault("params", {})
            # MECH-OAT-1 default in vibe19 is 60 F; use 55 F screening or 60 if evidence strong
            if hit.get("prohibited_mech_hours_below_60f", 0) > 100:
                params["oat_lockout_f"] = 60.0
            else:
                params.setdefault("oat_lockout_f", 55.0)
        measures.append(base)

    # Stable order: sched → lockout → sat → gl36
    order = [
        "ECM-AHU-SCHED-ALIGN",
        "ECM-CHILLER-LOCKOUT",
        "ECM-SAT-RESET",
        "ECM-GL36-AIRSIDE",
    ]
    measures.sort(
        key=lambda m: order.index(m["measure_id"])
        if m["measure_id"] in order
        else 99
    )

    return {
        "product": PRODUCT,
        "bundle_dir": str(root),
        "building_id": run_report.get("building_id"),
        "evidence": evidence,
        "measures": measures,
        "measure_ids": [m["measure_id"] for m in measures],
        "stats": {
            "fdd_rows": len(fdd),
            "evidence_count": len(evidence),
            "measure_count": len(measures),
            "prohibited_mech_hours_below_60f": prohibited_total,
        },
    }


def merge_into_profile(
    profile: dict[str, Any],
    bridge: dict[str, Any],
    *,
    replace_measures: bool = True,
) -> dict[str, Any]:
    """Attach vibe19 evidence + measures onto a WattLab building profile."""
    out = dict(profile)
    out["vibe19_evidence"] = {
        "evidence": bridge.get("evidence") or [],
        "bundle_dir": bridge.get("bundle_dir"),
        "stats": bridge.get("stats"),
    }
    suggested = list(bridge.get("measures") or [])
    if replace_measures or not out.get("measures"):
        out["measures"] = suggested
    else:
        existing_ids = {m.get("measure_id") for m in out.get("measures") or []}
        merged = list(out.get("measures") or [])
        for m in suggested:
            if m.get("measure_id") not in existing_ids:
                merged.append(m)
        out["measures"] = merged
    fs = dict(out.get("field_sources") or {})
    fs["measures"] = {
        "value": [m.get("measure_id") for m in out["measures"]],
        "source": "vibe19",
    }
    out["field_sources"] = fs
    prov = list(out.get("provenance") or [])
    prov.append(
        {
            "source": "vibe19_bridge",
            "bundle_dir": bridge.get("bundle_dir"),
            "measure_ids": bridge.get("measure_ids"),
        }
    )
    out["provenance"] = prov
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Map vibe19 export bundle → WattLab measures")
    p.add_argument("bundle", type=Path, help="Path to vibe19 agent-export directory")
    p.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Optional building profile to merge into",
    )
    p.add_argument("-o", "--out", type=Path, default=None, help="Write JSON report here")
    args = p.parse_args(argv)

    bridge = suggest_from_bundle(args.bundle)
    result: dict[str, Any] = {"bridge": bridge}
    if args.profile and args.profile.is_file():
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        result["profile"] = merge_into_profile(profile, bridge)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
