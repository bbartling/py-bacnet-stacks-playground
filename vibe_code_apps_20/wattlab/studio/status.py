"""Machine-readable Studio session status (agent-first).

``wattlab studio-status`` merges dump gaps ∩ answers ∩ bootstrap ∩ run
scorecard ∩ ecm_scenario into ``reports/session_status.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATUS_VERSION = 1
REQUIRED_ANSWER_FIELDS = ("building_type", "city", "floor_area_ft2")
OPTIONAL_ANSWER_FIELDS = ("floors", "lat", "lon", "wwr", "utility", "measure_set")
PHASE2_FIELDS = ("interval_meters", "tariffs", "carbon")


def answers_template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "answers.schema.template.json"


def ecm_scenario_template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "ecm_scenario.template.json"


def _truthy(val: Any) -> bool:
    return val not in (None, "", {}, [])


def _field_row(
    *,
    required: bool,
    dump: Any = None,
    answers: Any = None,
    phase: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"required": required}
    if phase is not None:
        row["phase"] = phase
    if dump is not None or (required and phase is None):
        row["dump"] = dump
    if answers is not None or _truthy(answers):
        row["answers"] = answers
    if phase == 2:
        row["status"] = "phase2" if not _truthy(answers) else "answered"
    elif _truthy(answers):
        row["status"] = "answered"
    elif _truthy(dump):
        row["status"] = "answered"
        row["note"] = note or "from dump"
    elif required:
        row["status"] = "missing"
    else:
        row["status"] = "missing"
    if note and "note" not in row:
        row["note"] = note
    return row


def answers_complete(answers: dict[str, Any] | None) -> bool:
    if not isinstance(answers, dict):
        return False
    return all(_truthy(answers.get(k)) for k in REQUIRED_ANSWER_FIELDS)


def profile_minimal_from_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Shape Twin form / resolve_profile expects."""
    minimal: dict[str, Any] = {
        "building_type": str(answers["building_type"]).strip(),
        "city": str(answers["city"]).strip(),
        "floor_area_ft2": float(answers["floor_area_ft2"]),
    }
    if _truthy(answers.get("floors")):
        minimal["floors"] = int(answers["floors"])
    if _truthy(answers.get("lat")):
        minimal["lat"] = float(answers["lat"])
    if _truthy(answers.get("lon")):
        minimal["lon"] = float(answers["lon"])
    if _truthy(answers.get("measure_set")):
        minimal["measure_set"] = str(answers["measure_set"])
    if isinstance(answers.get("utility"), dict):
        minimal["utility"] = answers["utility"]
    return minimal


def soften_required_gaps(
    gaps: list[dict[str, Any]],
    answers: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Mark dump required gaps answered when answers.json fills them."""
    if not answers:
        return list(gaps)
    out: list[dict[str, Any]] = []
    for g in gaps:
        row = dict(g)
        field = str(row.get("field") or "")
        if (
            row.get("severity") == "required"
            and row.get("status") == "missing"
            and field in REQUIRED_ANSWER_FIELDS
            and _truthy(answers.get(field))
        ):
            row["status"] = "answered"
            row["value"] = answers.get(field)
            row["via"] = "answers.json"
        # Align utility dual-view when answers.utility is filled
        if (
            field == "utility"
            and row.get("status") == "missing"
            and _truthy(answers.get("utility"))
        ):
            row["status"] = "answered"
            row["value"] = answers.get("utility")
            row["via"] = "answers.json"
        out.append(row)
    return out


def required_gaps_still_missing(
    gaps: list[dict[str, Any]],
    answers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    soft = soften_required_gaps(gaps, answers)
    return [
        g
        for g in soft
        if g.get("severity") == "required" and g.get("status") == "missing"
    ]


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_session_status(
    *,
    workspace: Path | None = None,
    dump_path: Path | str | None = None,
    answers_path: Path | str | None = None,
    bootstrap_path: Path | str | None = None,
    run_dir: Path | str | None = None,
    ecm_scenario_path: Path | str | None = None,
) -> dict[str, Any]:
    """Merge workspace artifacts into one agent-readable status sheet."""
    from wattlab.studio.bootstrap import resolve_bootstrap_path
    from wattlab.studio.ecm_scenario import load_ecm_scenario
    from wattlab.studio.workspace import ensure_workspace, reports_dir, runs_dir

    root = Path(workspace) if workspace is not None else ensure_workspace()
    boot_path = Path(bootstrap_path) if bootstrap_path else resolve_bootstrap_path(root)
    boot = _load_json(boot_path)

    ans_path = Path(answers_path) if answers_path else None
    if ans_path is None and boot.get("answers_path"):
        cand = Path(str(boot["answers_path"]))
        if not cand.is_absolute():
            cand = root / cand
        ans_path = cand if cand.is_file() else None
    reports = root / "reports"
    if ans_path is None:
        hit = reports / "answers.json"
        if hit.is_file():
            ans_path = hit
        else:
            # Any answers_*.json (sorted) — no preferred building-id filenames
            matches = sorted(reports.glob("answers_*.json"))
            if matches:
                ans_path = matches[0]
    answers = _load_json(ans_path)

    dump_p = Path(dump_path) if dump_path else None
    if dump_p is None and boot.get("dump_zip"):
        cand = Path(str(boot["dump_zip"]))
        if not cand.is_absolute():
            cand = root / cand
        dump_p = cand if cand.exists() else None

    gaps: list[dict[str, Any]] = []
    dump_seed: dict[str, Any] = {}
    building_id = None
    if dump_p is not None and dump_p.exists():
        try:
            from wattlab.seed import gap_report, load_bundle

            bundle = load_bundle(dump_p)
            gaps = gap_report(bundle)
            dump_seed = dict(bundle.model_seed or {})
            building_id = (
                dump_seed.get("building_id")
                or (bundle.building_profile or {}).get("building_id")
                or dump_p.stem
            )
        except Exception as exc:  # noqa: BLE001
            gaps = [{"field": "_dump", "severity": "required", "status": "blocked", "why": str(exc)}]

    soft_gaps = soften_required_gaps(gaps, answers)
    gap_by_field = {str(g.get("field")): g for g in soft_gaps}

    fields: dict[str, Any] = {}
    for name in REQUIRED_ANSWER_FIELDS:
        g = gap_by_field.get(name) or {}
        fields[name] = _field_row(
            required=True,
            dump=g.get("value") if g.get("status") in {"ok", "answered"} and not g.get("via") else dump_seed.get(name),
            answers=answers.get(name),
            note=g.get("via"),
        )
        if g.get("via") == "answers.json" and fields[name]["status"] == "answered":
            fields[name]["note"] = "answered via answers.json (dump null)"
    for name in OPTIONAL_ANSWER_FIELDS:
        g = gap_by_field.get(name) or {}
        fields[name] = _field_row(
            required=False,
            dump=g.get("value") if g.get("status") == "ok" else dump_seed.get(name),
            answers=answers.get(name),
        )
    for name in PHASE2_FIELDS:
        fields[name] = _field_row(required=False, phase=2, answers=answers.get(name))

    # utility_bills from dump gap, answers array, or reports CSV
    ub = gap_by_field.get("utility_bills") or {}
    bills_csv = root / "reports" / "utility_bills.csv"
    if ub.get("status") == "ok":
        fields["utility_bills"] = {
            "required": False,
            "status": "answered",
            "note": ub.get("value") or ub.get("why"),
        }
    elif _truthy(answers.get("utility_bills")):
        fields["utility_bills"] = {
            "required": False,
            "status": "answered",
            "note": "from answers.json",
            "answers": answers.get("utility_bills"),
        }
    elif bills_csv.is_file():
        fields["utility_bills"] = {
            "required": False,
            "status": "answered",
            "note": "reports/utility_bills.csv",
        }
    else:
        fields["utility_bills"] = {
            "required": False,
            "status": "missing",
            "note": ub.get("value") or ub.get("why"),
        }

    run_p: Path | None = Path(run_dir) if run_dir else None
    if run_p is None and boot.get("preferred_run_id"):
        cand = root / "runs" / str(boot["preferred_run_id"])
        if cand.is_dir():
            run_p = cand
    if run_p is None:
        pointer = root / "runs" / "CURRENT_RUN.txt"
        if pointer.is_file():
            try:
                p = Path(pointer.read_text(encoding="utf-8").strip())
                if p.is_dir():
                    run_p = p
            except OSError:
                pass

    scorecard: dict[str, Any] = {}
    if run_p is not None:
        scorecard = _load_json(run_p / "calibration_scorecard.json")
        if not scorecard:
            stamp = _load_json(run_p / "campaign_stamp.json")
            sp = stamp.get("scorecard_path")
            if sp and Path(str(sp)).is_file():
                scorecard = _load_json(Path(str(sp)))
            elif stamp:
                scorecard = stamp
        if not scorecard:
            report = _load_json(run_p / "wattlab_report.json")
            if report.get("utility_bills") or report.get("calibration"):
                scorecard = report
    g14_block: dict[str, Any] = {}
    bills = scorecard.get("utility_bills") or {}
    stats = bills.get("stats_electricity") or bills.get("stats") or {}
    if bills or stats or scorecard.get("pass_fail") or scorecard.get("status"):
        g14_block = {
            "overall": bills.get("pass_fail")
            or scorecard.get("pass_fail")
            or scorecard.get("status")
            or "n/a",
            "nmbe_elec_pct": stats.get("nmbe_pct"),
            "cvrmse_elec_pct": stats.get("cvrmse_pct"),
            "months_compared": bills.get("months_compared"),
        }

    ecm_path = Path(ecm_scenario_path) if ecm_scenario_path else None
    if ecm_path is None and boot.get("ecm_scenario_path"):
        cand = Path(str(boot["ecm_scenario_path"]))
        if not cand.is_absolute():
            cand = root / cand
        ecm_path = cand
    if ecm_path is None:
        default_ecm = root / "reports" / "ecm_scenario.json"
        if default_ecm.is_file():
            ecm_path = default_ecm
    ecm = load_ecm_scenario(ecm_path)

    return {
        "version": STATUS_VERSION,
        "building_id": building_id or answers.get("building_id"),
        "paths": {
            "workspace": str(root),
            "bootstrap": str(boot_path) if boot_path else None,
            "answers": str(ans_path) if ans_path else None,
            "dump": str(dump_p) if dump_p else None,
            "preferred_run": str(run_p) if run_p else None,
            "ecm_scenario": str(ecm_path or (root / "reports" / "ecm_scenario.json")),
        },
        "fields": fields,
        "twin": {
            "profile_resolvable": answers_complete(answers),
            "preferred_run_id": boot.get("preferred_run_id") or (run_p.name if run_p else None),
            "g14": g14_block or None,
        },
        "ecm_scenario": {
            "source": "agent" if ecm.get("selected_ecm_ids") else "empty",
            "selected_ecm_ids": ecm.get("selected_ecm_ids") or [],
            "measure_set": ecm.get("measure_set"),
            "status": ecm.get("status"),
            "recommendations": ecm.get("recommendations") or [],
        },
        "gaps_softened": soft_gaps,
    }


def write_session_status(
    status: dict[str, Any] | None = None,
    *,
    workspace: Path | None = None,
    path: Path | None = None,
) -> Path:
    from wattlab.studio.workspace import ensure_workspace, reports_dir

    root = Path(workspace) if workspace is not None else ensure_workspace()
    out = path or (root / "reports" / "session_status.json")
    if workspace is None and path is None:
        out = reports_dir() / "session_status.json"
    payload = status if status is not None else build_session_status(workspace=workspace)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(
        description="Merge dump/answers/bootstrap/run/ecm into session_status.json"
    )
    p.add_argument("--write", action="store_true", help="write reports/session_status.json")
    p.add_argument("--dump", type=Path, default=None)
    p.add_argument("--answers", type=Path, default=None)
    p.add_argument("--run", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--template", action="store_true", help="print answers schema template path")
    args = p.parse_args(argv)

    if args.template:
        print(json.dumps({"answers_template": str(answers_template_path())}, indent=2))
        return 0

    status = build_session_status(
        dump_path=args.dump,
        answers_path=args.answers,
        run_dir=args.run,
    )
    if args.write or args.out:
        written = write_session_status(status, path=args.out)
        print(json.dumps({"ok": True, "written": str(written), "status": status}, indent=2, default=str))
    else:
        print(json.dumps(status, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
