"""Weather-triggered continuous-conditioning two-month replay CLI."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.rl.weather_trigger_publish import publish_weather_pack  # noqa: E402
from eplus_gym.rl.weather_trigger_replay import (  # noqa: E402
    POLICY_IDS,
    import_two_month_reference,
    run_weather_policy,
)
from eplus_gym.rl.weather_trigger_select import load_weather_trigger_contract  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _worker(payload: dict[str, Any]) -> dict[str, Any]:
    from eplus_gym.site_env import require_site_root

    site = require_site_root(Path(payload["site_root"]) if payload.get("site_root") else None)
    return run_weather_policy(
        site=site,
        app_root=_APP,
        out_dir=Path(payload["out_dir"]),
        policy_id=str(payload["policy_id"]),
    )


def _run_sub(*, site: Path, site_out: Path, policy_id: str) -> dict[str, Any]:
    payload = {
        "site_root": str(site),
        "out_dir": str(site_out / policy_id),
        "policy_id": policy_id,
    }
    tmp = site_out / f"_worker_{policy_id}.json"
    res = site_out / f"_result_{policy_id}.json"
    _save(tmp, payload)
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--worker-json",
        str(tmp),
        "--result-json",
        str(res),
    ]
    print(f"policy: {policy_id}", flush=True)
    proc = subprocess.run(cmd, cwd=str(_APP), capture_output=True, text=True)
    if proc.returncode != 0 or not res.is_file():
        return {
            "strategy": policy_id,
            "policy_id": policy_id,
            "status": "FAILED",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:],
        }
    return _load(res)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--strategy", default="all", help="all or one POLICY_ID")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--publish-only", action="store_true")
    p.add_argument("--site-run-dir", type=Path, default=None)
    p.add_argument(
        "--two-month-site-run",
        type=Path,
        default=None,
        help="SITE two-month replay dir for importing reference arms",
    )
    p.add_argument("--worker-json", type=Path, default=None)
    p.add_argument("--result-json", type=Path, default=None)
    args = p.parse_args()

    if args.worker_json is not None:
        payload = _load(Path(args.worker_json))
        result = _worker(payload)
        out = Path(args.result_json) if args.result_json else Path(args.worker_json).with_name("_result.json")
        _save(out, result)
        return 0

    from eplus_gym.site_env import require_site_root

    site = require_site_root(args.site_root)
    contract = load_weather_trigger_contract(_APP)
    run_dir = args.site_run_dir or (site / "reports/eplus_gym/rl" / f"weather_trigger_{_utc()}")
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "run_manifest_site.json"
    state = _load(state_path) if args.resume or args.publish_only else {"completed": {}}

    policies = list(POLICY_IDS) if args.strategy == "all" else [args.strategy]
    if not args.publish_only:
        for pid in policies:
            if args.resume and (state.get("completed") or {}).get(pid, {}).get("status") == "OK":
                print(f"skip {pid}", flush=True)
                continue
            result = _run_sub(site=site, site_out=run_dir, policy_id=pid)
            state.setdefault("completed", {})[pid] = {
                "status": result.get("status"),
                "trajectory_hash": result.get("trajectory_hash"),
                "elapsed_s": result.get("elapsed_s"),
                "n_intervals": result.get("n_intervals"),
            }
            if result.get("status") != "OK":
                _save(state_path, state)
                print(json.dumps(result, indent=2)[:2000], file=sys.stderr)
                return 1
            _save(state_path, state)

    # Load results
    results: dict[str, Any] = {}
    for pid in POLICY_IDS:
        rpath = run_dir / pid / "result.json"
        if rpath.is_file():
            results[pid] = _load(rpath)

    # Import reference arms
    tm = args.two_month_site_run
    if tm is None:
        # prefer path recorded in two_month pack
        man = _APP / "docs/results/two_month_policy_replay/run_manifest.json"
        if man.is_file():
            tm = Path(_load(man).get("site_run_dir") or "")
    if tm and Path(tm).is_dir():
        for ref in contract.get("reference_strategies_import") or []:
            if ref in results:
                continue
            try:
                results[ref] = import_two_month_reference(two_month_site_run=Path(tm), strategy=ref)
            except FileNotFoundError as exc:
                print(f"warn: {exc}", file=sys.stderr)

    if not results:
        print("no results to publish", file=sys.stderr)
        return 1

    # Nightly compute facts for fig10
    nightly_man = _APP / "docs/results/nightly_grid_compute/run_manifest.json"
    compute_facts: dict[str, Any] = {}
    if nightly_man.is_file():
        nm = _load(nightly_man)
        compute_facts["nightly_exhaustive_s"] = nm.get("sequential_exhaustive_candidate_compute_s") or nm.get(
            "exhaustive_wall_s"
        )
    pack = publish_weather_pack(
        app_root=_APP,
        site=site,
        site_run_dir=run_dir,
        results=results,
        compute_facts=compute_facts,
    )
    # artifact index
    idx_path = _APP / "docs/results/artifact_index_v1.json"
    idx = _load(idx_path)
    items = idx.get("items") or []
    if not any(i.get("path") == "docs/results/weather_trigger_continuous/" for i in items):
        items.append(
            {
                "path": "docs/results/weather_trigger_continuous/",
                "status": "ACTIVE_RESEARCH_SCREEN",
                "notes": "Weather-triggered continuous 68/74 retrospective screen; not operational DSM",
            }
        )
        idx["items"] = items
        _save(idx_path, idx)
    print(json.dumps({"pack": str(pack), "n_results": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
