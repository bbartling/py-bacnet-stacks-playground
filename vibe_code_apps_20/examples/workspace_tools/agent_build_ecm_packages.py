#!/usr/bin/env python3
"""Agent-driven ECM Excel: build notebook packages against a calibrated Twin.

Wraps ``wattlab notebook agent-build`` for one or more package ids. Picks the
best G14-pass Twin via ``pick_best_twin_run.py`` unless ``--twin-run`` is set.

Writes under ``reports/notebooks/{file_stem}.xlsx`` (+ manifests). Soft Twin paste:
Calibrated_Twin gets G14 baseline; measure EPlus_Results stay blank when no
``savings_by_measure`` (never fatal).

# Default 3-scenario ladder (example site — G36 airside → plant → envelope)::
#
#   docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \\
#     python /data/tools/agent_build_ecm_packages.py \\
#       --answers /data/reports/answers_building_100_geo.json \\
#       --prefix geo_b100 \\
#       --packages g36_airside_controls,plant_optimization,envelope_code \\
#       --fan-hp 80 \\
#       --write-scenario
#
# Writes:
#   01_G36_DSP_SAT_chiller_lockout.xlsx   (DSP + SAT + lockout <60°F)
#   03_plant_chiller_boiler_erv.xlsx
#   04_envelope_code_windows_insulation.xlsx
#
# Optional deep DOAS/HP: add ``deep_retrofit`` to --packages or run alone.
#
# Savings target (when E+ cascade exists):
#   per ECM kWh/therms saved = calibrated baseline annual − ECM-on-Twin annual
#   → savings_by_measure → Twin_Measures / Crosscheck (vs ESCO Calc_*)
#
# One-command build (BUG-063):
#   ESCO-only (no EnergyPlus, always succeeds):
#     python agent_build_ecm_packages.py --answers ... --prefix geo_b100
#   Force the E+ measure cascade (requires docker + energyplus-mcp-dev image):
#     python agent_build_ecm_packages.py --answers ... --prefix geo_b100 --cascade
#   Cascade only when the environment is ready, else fall back to ESCO-only with
#   a clear skip reason + honesty stamp (never fails the build):
#     python agent_build_ecm_packages.py --answers ... --prefix geo_b100 --cascade-if-ready
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent

# Default package ladder: easy controls → G36 airside → plant/ERV → envelope code
DEFAULT_PACKAGES = (
    "g36_airside_controls",
    "plant_optimization",
    "envelope_code",
)

# EnergyPlus MCP dev image + docker socket required for an automatic cascade.
DEFAULT_EP_IMAGE = "energyplus-mcp-dev"
DOCKER_SOCK = Path("/var/run/docker.sock")


def cascade_ready(image: str = DEFAULT_EP_IMAGE) -> tuple[bool, str]:
    """BUG-063: True only when a real E+ cascade could run right now.

    Requires (1) a Docker daemon socket at ``/var/run/docker.sock`` and (2) the
    EnergyPlus MCP image present (``docker image inspect`` succeeds). Returns
    ``(ready, reason)`` so callers can print a clear skip reason and continue
    ESCO-only instead of failing the build.
    """
    if not DOCKER_SOCK.exists():
        return False, f"{DOCKER_SOCK} not found (no Docker daemon reachable)"
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False, "docker CLI not found on PATH"
    if proc.returncode != 0:
        return False, f"docker image '{image}' not available (run its build first)"
    return True, f"{DOCKER_SOCK} present and image '{image}' available"


def _pick_twin(workspace: Path, *, prefix: str | None, twin_run: str | None) -> dict[str, Any]:
    cmd = [sys.executable, str(TOOLS / "pick_best_twin_run.py"), "--workspace", str(workspace), "--json"]
    if twin_run:
        p = Path(twin_run)
        if p.is_dir():
            cmd += ["--run-dir", str(p)]
        else:
            cmd += ["--run-id", str(twin_run)]
    elif prefix:
        cmd += ["--prefix", prefix]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "pick_best_twin_run failed")
    return json.loads(proc.stdout)


def _wattlab_cmd() -> list[str]:
    # Prefer installed CLI inside vibe20 / host venv
    return ["wattlab", "notebook", "agent-build"]


def build_one(
    *,
    package: str,
    answers: Path,
    twin_run: Path,
    out_dir: Path,
    fan_hp: float | None,
    write_scenario: bool,
    ecms: str | None,
    extra_env: dict[str, str],
) -> dict[str, Any]:
    cmd = _wattlab_cmd() + [
        "--package",
        package,
        "--answers",
        str(answers),
        "--twin-run",
        str(twin_run),
        "--out",
        str(out_dir),
    ]
    if fan_hp is not None:
        cmd += ["--fan-hp", str(fan_hp)]
    if ecms:
        cmd += ["--ecms", ecms]
    if write_scenario:
        cmd.append("--write-scenario")
    env = {**os.environ, **extra_env}
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    payload: dict[str, Any] = {
        "package": package,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            payload["result"] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            pass
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", type=Path, default=Path(os.environ.get("WATTLAB_STUDIO_WORKSPACE", "/data")))
    p.add_argument("--answers", type=Path, required=True, help="answers.json / profile merge source")
    p.add_argument(
        "--packages",
        default=",".join(DEFAULT_PACKAGES),
        help="Comma package ids (default: 4-act easy→G36→plant→envelope)",
    )
    p.add_argument("--prefix", default=None, help="runs/ filter for best Twin (e.g. geo_b100)")
    p.add_argument("--twin-run", default=None, help="Override Twin run id or path")
    p.add_argument("--out", type=Path, default=None, help="Default: <workspace>/reports/notebooks")
    p.add_argument("--fan-hp", type=float, default=None)
    p.add_argument("--ecms", default=None, help="Optional comma measure ids (applied to every package)")
    p.add_argument("--write-scenario", action="store_true", help="Update ecm_scenario.json (last package)")
    p.add_argument(
        "--cascade",
        action="store_true",
        help="Run E+ measure cascade on Twin first (writes savings_by_measure to wattlab_report.json)",
    )
    p.add_argument(
        "--cascade-if-ready",
        action="store_true",
        help=(
            "Auto-cascade only if /var/run/docker.sock exists AND the "
            f"'{DEFAULT_EP_IMAGE}' image is present; otherwise print a skip "
            "reason and continue ESCO-only (never fails the build)."
        ),
    )
    p.add_argument(
        "--ep-image",
        default=DEFAULT_EP_IMAGE,
        help=f"EnergyPlus MCP image checked by --cascade-if-ready (default: {DEFAULT_EP_IMAGE})",
    )
    p.add_argument("--dry-run-cascade", action="store_true", help="With --cascade: plan only, no EP")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    workspace = args.workspace
    out_dir = args.out or (workspace / "reports" / "notebooks")
    out_dir.mkdir(parents=True, exist_ok=True)

    twin = _pick_twin(workspace, prefix=args.prefix, twin_run=args.twin_run)
    if not twin.get("run_dir"):
        print(json.dumps(twin, indent=2), file=sys.stderr)
        return 2

    packages = [x.strip() for x in str(args.packages).split(",") if x.strip()]
    env = {"WATTLAB_STUDIO_WORKSPACE": str(workspace)}

    # BUG-063: resolve whether we actually run the cascade. --cascade forces it;
    # --cascade-if-ready only runs it when docker + the E+ image are present, and
    # otherwise falls back to ESCO-only with a clear skip reason (never fatal).
    run_cascade = bool(args.cascade)
    cascade_skip_reason: str | None = None
    if args.cascade_if_ready and not run_cascade:
        ready, reason = cascade_ready(args.ep_image)
        if ready:
            run_cascade = True
            print(f"[cascade-if-ready] {reason} — running E+ cascade", file=sys.stderr)
        else:
            cascade_skip_reason = reason
            print(
                f"[cascade-if-ready] skipping cascade: {reason} — "
                "continuing ESCO-only (honesty stamp applied)",
                file=sys.stderr,
            )

    cascade_result = None
    if run_cascade and packages:
        from wattlab.notebooks.packages import get_notebook_package
        from wattlab.notebooks.twin_cascade import cascade_measures_on_twin

        profile = json.loads(args.answers.read_text(encoding="utf-8")) if args.answers.is_file() else {}
        measure_ids = list(get_notebook_package(packages[0]).measure_ids)
        try:
            cascade_result = cascade_measures_on_twin(
                Path(twin["run_dir"]),
                measure_ids,
                profile=profile,
                dry_run=bool(args.dry_run_cascade),
            )
        except Exception as exc:
            cascade_result = {"ok": False, "error": str(exc)}
    builds: list[dict[str, Any]] = []
    for i, pkg in enumerate(packages):
        write_scen = bool(args.write_scenario and i == len(packages) - 1)
        builds.append(
            build_one(
                package=pkg,
                answers=args.answers,
                twin_run=Path(twin["run_dir"]),
                out_dir=out_dir,
                fan_hp=args.fan_hp,
                write_scenario=write_scen,
                ecms=args.ecms,
                extra_env=env,
            )
        )

    summary = {
        "twin": {k: twin.get(k) for k in (
            "run_id", "run_dir", "g14_pass", "cvrmse_mean", "model_site_eui",
            "model_kwh", "model_therms", "selection", "warning",
        ) if k in twin},
        "out_dir": str(out_dir),
        "packages": packages,
        "builds": builds,
        "cascade": cascade_result,
        "cascade_requested": run_cascade,
        "cascade_skip_reason": cascade_skip_reason,
        "cascade_mode": (
            "forced" if args.cascade else ("if_ready" if args.cascade_if_ready else "off")
        ),
        "ok": all(b.get("returncode") == 0 for b in builds)
        and (
            cascade_result is None
            or cascade_result.get("dry_run")
            or cascade_result.get("savings_by_measure") is not None
        ),
        "studio_hint": "Studio ECMs → Reload from disk → Screening results (numbers only)",
        "savings_honesty": (
            "Calibrated savings = baseline Twin − ECM-on-Twin when savings_by_measure exists; "
            "else Screening_Results = ESCO/proxy until BUG-048/049 cascade fixed"
        ),
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
