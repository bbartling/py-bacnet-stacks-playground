"""Two-month frozen-policy replay CLI — subprocess per strategy."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.rl.two_month_provenance import build_provenance  # noqa: E402
from eplus_gym.rl.two_month_publish import publish_pack  # noqa: E402
from eplus_gym.rl.two_month_replay import STRATEGIES, run_strategy  # noqa: E402


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _worker(payload: dict[str, Any]) -> dict[str, Any]:
    from eplus_gym.site_env import require_site_root

    site = require_site_root(Path(payload["site_root"]) if payload.get("site_root") else None)
    strategy = str(payload["strategy"])
    site_out = Path(payload["site_out"])
    return run_strategy(strategy=strategy, site=site, app_root=_APP, site_out=site_out)


def _run_subprocess(*, site: Path, site_out: Path, strategy: str) -> dict[str, Any]:
    payload = {"site_root": str(site), "site_out": str(site_out), "strategy": strategy}
    tmp = site_out / f"_worker_{strategy}.json"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    result_path = site_out / f"_result_{strategy}.json"
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--worker-json",
        str(tmp),
        "--result-json",
        str(result_path),
    ]
    print(f"strategy: {strategy}", flush=True)
    proc = subprocess.run(cmd, cwd=str(_APP), capture_output=True, text=True)
    if proc.returncode != 0:
        return {
            "strategy": strategy,
            "status": "FAILED",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:],
        }
    return json.loads(result_path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"completed": {}}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--strategy", default="all", help="all or one of: " + ",".join(STRATEGIES))
    p.add_argument("--worker-json", type=Path, default=None)
    p.add_argument("--result-json", type=Path, default=None)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--publish-only", action="store_true", help="Rebuild repo pack from SITE_ROOT results")
    p.add_argument("--site-run-dir", type=Path, default=None)
    args = p.parse_args()

    if args.worker_json is not None:
        payload = json.loads(Path(args.worker_json).read_text(encoding="utf-8"))
        result = _worker(payload)
        out = Path(args.result_json) if args.result_json else Path(args.worker_json).with_name("_result.json")
        out.write_text(json.dumps(result), encoding="utf-8")
        return 0

    from eplus_gym.site_env import require_site_root

    site = require_site_root(args.site_root)
    run_dir = args.site_run_dir or (site / "reports/eplus_gym/rl" / f"two_month_replay_{_utc_stamp()}")
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest_site.json"
    manifest = _load_manifest(manifest_path)

    if args.publish_only:
        results = {}
        for s in STRATEGIES:
            rp = run_dir / s / "result.json"
            if rp.is_file():
                results[s] = json.loads(rp.read_text(encoding="utf-8"))
        if not results:
            print("No completed strategy results found", file=sys.stderr)
            return 1
        pack = publish_pack(app_root=_APP, site=site, results=results, site_run_dir=run_dir)
        print(json.dumps({"pack": str(pack), "n_strategies": len(results)}, indent=2))
        return 0

    prov = build_provenance(app_root=_APP, site=site)
    (run_dir / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")

    selected = list(STRATEGIES) if args.strategy == "all" else [args.strategy.strip()]
    for s in selected:
        if s not in STRATEGIES:
            raise SystemExit(f"unknown strategy {s!r}")
    results: dict[str, Any] = {}
    t0 = time.perf_counter()
    for s in selected:
        if args.resume and manifest.get("completed", {}).get(s):
            rp = run_dir / s / "result.json"
            if rp.is_file():
                print(f"resume skip {s}", flush=True)
                results[s] = json.loads(rp.read_text(encoding="utf-8"))
                continue
        r = _run_subprocess(site=site, site_out=run_dir, strategy=s)
        if r.get("status") == "FAILED":
            manifest.setdefault("failures", {})[s] = r
            (manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(json.dumps(r, indent=2), file=sys.stderr)
            return 1
        results[s] = r
        manifest.setdefault("completed", {})[s] = {
            "trajectory_hash": r.get("trajectory_hash"),
            "n_intervals": r.get("n_intervals"),
            "elapsed_s": r.get("elapsed_s"),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    pack = publish_pack(app_root=_APP, site=site, results=results, site_run_dir=run_dir)
    summary = {
        "site_run_dir": str(run_dir),
        "pack_dir": str(pack),
        "strategies": list(results.keys()),
        "elapsed_s": time.perf_counter() - t0,
        "bacnet_commands": 0,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
