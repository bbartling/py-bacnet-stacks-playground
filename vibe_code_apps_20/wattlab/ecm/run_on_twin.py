"""Run ECMs on the best G14-calibrated Twin via EnergyPlus (MCP/DinD simulate).

This is the Easy-Button path for *calibrated* models — not the prototype
progressive cascade. Spreadsheet side is prepared in ecm_compare.json but left
empty until external ESCO workbooks land.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_G36_ECMS = (
    "ECM-DSP-RESET",
    "ECM-SAT-RESET",
    "ECM-CHILLER-LOCKOUT",
)


def pick_best_twin_dir(
    workspace: Path | str,
    *,
    prefix: str | None = None,
    twin_run: str | Path | None = None,
) -> Path:
    """Resolve a twin run directory (explicit path/id or pick_best tool)."""
    workspace = Path(workspace)
    if twin_run:
        p = Path(twin_run)
        if p.is_dir() and (p / "model.idf").is_file():
            return p
        cand = workspace / "runs" / str(twin_run)
        if cand.is_dir() and (cand / "model.idf").is_file():
            return cand
        raise FileNotFoundError(f"Twin run not found: {twin_run}")

    tools = workspace / "tools" / "pick_best_twin_run.py"
    if tools.is_file():
        import subprocess
        import sys

        cmd = [sys.executable, str(tools), "--workspace", str(workspace), "--json"]
        if prefix:
            cmd += ["--prefix", prefix]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            run_dir = data.get("run_dir") or data.get("path")
            if run_dir:
                return Path(run_dir)
    # Fallback: first runs/*/model.idf
    runs = workspace / "runs"
    if runs.is_dir():
        for d in sorted(runs.iterdir(), reverse=True):
            if d.is_dir() and (d / "model.idf").is_file():
                return d
    raise FileNotFoundError(f"No calibrated twin under {workspace}/runs")


def run_ecms_on_twin(
    *,
    workspace: Path | str,
    measure_ids: list[str] | None = None,
    twin_run: str | Path | None = None,
    prefix: str | None = None,
    profile: dict[str, Any] | None = None,
    answers_path: Path | str | None = None,
    dry_run: bool = False,
    write_compare: bool = True,
) -> dict[str, Any]:
    """Patch+simulate each ECM on best Twin; write reports/ecm_compare.json."""
    from wattlab.ecm.compare import (
        build_compare_from_cascade,
        compare_path,
        merge_full_parity_ss,
        write_compare as _write,
    )
    from wattlab.notebooks.twin_cascade import cascade_measures_on_twin

    workspace = Path(workspace)
    profile = dict(profile or {})
    if answers_path:
        ap = Path(answers_path)
        if ap.is_file():
            profile.update(json.loads(ap.read_text(encoding="utf-8")))

    twin_dir = pick_best_twin_dir(workspace, prefix=prefix, twin_run=twin_run)
    mids = list(measure_ids) if measure_ids else list(DEFAULT_G36_ECMS)

    # Pass lockout at 60°F to match G36 notebook / product story
    # (cascade reads patch params from catalog — override via profile measures if present)
    if dry_run:
        plan = cascade_measures_on_twin(twin_dir, mids, profile=profile, dry_run=True)
        stub = build_compare_from_cascade(
            {"savings_by_measure": [], "twin_run": twin_dir.name, "weather_suitability": plan.get("weather_suitability")},
            measure_ids=mids,
            twin_run=twin_dir.name,
        )
        stub["energyplus"]["status"] = "dry_run"
        merge_full_parity_ss(stub, workspace / "reports")
        out: dict[str, Any] = {
            "ok": True,
            "dry_run": True,
            "twin_run": twin_dir.name,
            "twin_dir": str(twin_dir),
            "measure_ids": mids,
            "plan": plan,
            "compare": stub,
        }
        if write_compare:
            out["compare_path"] = str(_write(compare_path(workspace / "reports"), stub))
        return out

    report = cascade_measures_on_twin(twin_dir, mids, profile=profile, dry_run=False)
    compare = build_compare_from_cascade(
        report,
        measure_ids=mids,
        twin_run=twin_dir.name,
        cascade_dir=report.get("out_dir"),
        profile=profile,
    )
    merge_full_parity_ss(compare, workspace / "reports")
    result: dict[str, Any] = {
        "ok": True,
        "dry_run": False,
        "twin_run": twin_dir.name,
        "twin_dir": str(twin_dir),
        "measure_ids": mids,
        "report_path": report.get("report_path"),
        "out_dir": report.get("out_dir"),
        "compare": compare,
    }
    if write_compare:
        cpath = _write(compare_path(workspace / "reports"), compare)
        result["compare_path"] = str(cpath)
        twin_rep = twin_dir / "wattlab_report.json"
        if twin_rep.is_file():
            try:
                existing = json.loads(twin_rep.read_text(encoding="utf-8"))
                existing["ecm_compare_path"] = str(cpath)
                twin_rep.write_text(json.dumps(existing, indent=2, default=str) + "\n", encoding="utf-8")
            except Exception:
                pass
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Run ECMs on best calibrated Twin (EnergyPlus MCP/DinD)"
    )
    p.add_argument("--workspace", default="/data", help="WattLab workspace root")
    p.add_argument("--twin-run", default=None, help="Run id or path (else pick best)")
    p.add_argument("--prefix", default=None, help="pick_best prefix filter")
    p.add_argument("--answers", default=None, help="answers/profile JSON")
    p.add_argument(
        "--ecms",
        default=",".join(DEFAULT_G36_ECMS),
        help="Comma-separated measure ids",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    mids = [x.strip() for x in str(args.ecms).split(",") if x.strip()]
    result = run_ecms_on_twin(
        workspace=args.workspace,
        measure_ids=mids,
        twin_run=args.twin_run,
        prefix=args.prefix,
        answers_path=args.answers,
        dry_run=args.dry_run,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "cascade"}, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
