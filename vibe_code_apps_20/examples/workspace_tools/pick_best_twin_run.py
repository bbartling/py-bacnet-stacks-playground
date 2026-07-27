#!/usr/bin/env python3
"""Pick the best calibrated Twin run under ``runs/`` (G14-first).

Preference order:
  1. Explicit ``--run-id`` / ``--run-dir`` if it exists
  2. Runs with ``g14_pass`` / utility_bills PASS (both fuels)
  3. Among PASS: lowest mean(elec_cvrmse, gas_cvrmse)
  4. Else: warn and fall back to CURRENT.json source_run_id, then newest run

Does **not** hardcode Liberty — pass ``--prefix geo_b100`` (or similar) to filter.

Example::

  docker exec vibe20 python /data/tools/pick_best_twin_run.py \\
    --workspace /data --prefix geo_b100 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _g14_block(run_dir: Path) -> dict[str, Any]:
    for name in ("g14_score.json", "report.json", "wattlab_report.json", "calibration_scorecard.json"):
        data = _load(run_dir / name) or {}
        if name == "g14_score.json" and data:
            return data
        g14 = data.get("g14")
        if isinstance(g14, dict) and g14:
            return g14
        ub = data.get("utility_bills")
        if isinstance(ub, dict) and ub.get("pass_fail"):
            return {
                "g14_pass": str(ub.get("pass_fail")).upper() == "PASS",
                "elec": (ub.get("stats_electricity") or {}),
                "gas": (ub.get("stats_natural_gas") or {}),
            }
    return {}


def _scorecard(run_dir: Path) -> dict[str, Any]:
    return _load(run_dir / "scorecard.json") or {}


def _is_pass(g14: dict[str, Any], score: dict[str, Any]) -> bool:
    if g14.get("g14_pass") is True:
        return True
    if g14.get("elec_pass") is True and g14.get("gas_pass") is True:
        return True
    pf = score.get("pass_fail") or (score.get("utility_bills") or {}).get("pass_fail")
    return str(pf or "").upper() == "PASS"


def _cv_mean(g14: dict[str, Any]) -> float:
    elec = g14.get("elec") if isinstance(g14.get("elec"), dict) else {}
    gas = g14.get("gas") if isinstance(g14.get("gas"), dict) else {}
    vals = []
    for block in (elec, gas):
        try:
            vals.append(float(block.get("cvrmse_pct")))
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else 999.0


def rank_runs(
    workspace: Path,
    *,
    prefix: str | None = None,
) -> list[dict[str, Any]]:
    runs_root = workspace / "runs"
    if not runs_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for d in sorted(runs_root.iterdir()):
        if not d.is_dir():
            continue
        if prefix and not d.name.startswith(prefix):
            continue
        if not (d / "model.idf").is_file() and not (d / "scorecard.json").is_file():
            continue
        g14 = _g14_block(d)
        score = _scorecard(d)
        passed = _is_pass(g14, score)
        rows.append(
            {
                "run_id": d.name,
                "run_dir": str(d),
                "g14_pass": passed,
                "cvrmse_mean": round(_cv_mean(g14), 3),
                "model_site_eui": score.get("model_site_eui"),
                "model_kwh": score.get("model_kwh"),
                "model_therms": score.get("model_therms"),
                "has_savings_by_measure": bool(
                    (_load(d / "report.json") or {}).get("savings_by_measure")
                ),
            }
        )
    rows.sort(key=lambda r: (0 if r["g14_pass"] else 1, r["cvrmse_mean"], r["run_id"]))
    return rows


def pick_best(
    workspace: Path,
    *,
    prefix: str | None = None,
    run_id: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    if run_dir:
        p = Path(run_dir)
        if not p.is_absolute():
            p = workspace / p
        if p.is_dir():
            ranked = rank_runs(p.parent, prefix=None)
            for row in ranked:
                if Path(row["run_dir"]) == p.resolve() or row["run_id"] == p.name:
                    return {**row, "selection": "explicit_run_dir"}
            g14 = _g14_block(p)
            score = _scorecard(p)
            return {
                "run_id": p.name,
                "run_dir": str(p),
                "g14_pass": _is_pass(g14, score),
                "cvrmse_mean": round(_cv_mean(g14), 3),
                "model_site_eui": score.get("model_site_eui"),
                "model_kwh": score.get("model_kwh"),
                "model_therms": score.get("model_therms"),
                "has_savings_by_measure": bool(
                    (_load(p / "report.json") or {}).get("savings_by_measure")
                ),
                "selection": "explicit_run_dir",
            }
    if run_id:
        p = workspace / "runs" / run_id
        if p.is_dir():
            return pick_best(workspace, run_dir=str(p))

    ranked = rank_runs(workspace, prefix=prefix)
    if ranked and ranked[0]["g14_pass"]:
        return {**ranked[0], "selection": "g14_pass_best_cv", "candidates": ranked[:8]}

    current = _load(workspace / "uploads" / "prototypes" / "best" / "CURRENT.json") or {}
    src = current.get("source_run_id")
    if src:
        p = workspace / "runs" / str(src)
        if p.is_dir():
            row = pick_best(workspace, run_dir=str(p))
            row["selection"] = "current_json_fallback"
            row["current_note"] = current.get("note")
            row["warning"] = (
                "No G14-pass run matched; using uploads/prototypes/best/CURRENT.json "
                f"source_run_id={src}"
            )
            return row

    if ranked:
        return {
            **ranked[0],
            "selection": "best_available_non_pass",
            "warning": "No G14-pass run found; returning lowest-CV candidate",
            "candidates": ranked[:8],
        }
    return {"error": "no runs found", "run_dir": None, "g14_pass": False}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", type=Path, default=Path("/data"))
    p.add_argument("--prefix", default=None, help="Filter runs/ ids (e.g. geo_b100)")
    p.add_argument("--run-id", default=None)
    p.add_argument("--run-dir", default=None)
    p.add_argument("--list", action="store_true", help="Print ranked candidates")
    p.add_argument("--json", action="store_true", help="JSON stdout")
    args = p.parse_args(argv)

    if args.list:
        rows = rank_runs(args.workspace, prefix=args.prefix)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows[:25]:
                flag = "PASS" if r["g14_pass"] else "fail"
                print(
                    f"{r['run_id']}\t{flag}\tcv={r['cvrmse_mean']}\t"
                    f"eui={r.get('model_site_eui')}"
                )
        return 0

    best = pick_best(
        args.workspace,
        prefix=args.prefix,
        run_id=args.run_id,
        run_dir=args.run_dir,
    )
    print(json.dumps(best, indent=2))
    return 0 if best.get("run_dir") else 2


if __name__ == "__main__":
    raise SystemExit(main())
