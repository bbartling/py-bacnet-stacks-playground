"""Immutable A04 baseline freeze for A04-v2 transient work (Phase 0)."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_LF
from eplus_gym.rl.physics_ramp_gate import ENGINEERING_MARGIN
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import sha256_file


class Phase0Error(RuntimeError):
    """Fail-closed provenance: git SHA or EPW cannot be pinned."""


def git_head(repo: Path) -> str:
    g = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    head = (g.stdout or "").strip()
    if g.returncode != 0 or not head:
        raise Phase0Error(f"git rev-parse HEAD failed: {(g.stderr or '').strip()}")
    return head


def freeze_baseline(*, app: Path, site: Path) -> dict:
    idf = app / "models" / "eplus" / A04_IDF_NAME
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if not epw.is_file():
        raise Phase0Error(f"EPW missing: {epw}")
    ramp_path = app / "docs" / "audits" / "figures" / "postfix" / "ramp_gate.json"
    ramp = json.loads(ramp_path.read_text(encoding="utf-8"))
    raw = idf.read_bytes()
    idf_sha = sha256_file(idf)
    lf = __import__("hashlib").sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if idf_sha not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise Phase0Error(f"A04 hash mismatch: {idf_sha}")
    out_dir = app / "docs" / "audits" / "figures" / "a04v2" / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_path = out_dir / f"IMMUTABLE_{A04_IDF_NAME}"
    if not copy_path.is_file() or sha256_file(copy_path) != idf_sha:
        copy_path.write_bytes(raw)
    head = git_head(app.parent)
    return {
        "schema": "vibe22.a04v2.phase0_baseline.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": head,
        "branch_note": "stacked on PR #97 tip a5f6e770 (includes #96); #96/#97 still OPEN on develop",
        "a04": {
            "filename": A04_IDF_NAME,
            "sha256": idf_sha,
            "immutable_copy": str(copy_path.relative_to(app)).replace("\\", "/"),
            "role": "immutable_parent_comparison_baseline",
        },
        "epw": {
            "path": "<SITE_ROOT>/eplus/weather/madison_amy_202508_202608.epw",
            "sha256": sha256_file(epw),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor(),
            "energyplus": "26.1.0",
        },
        "january_holdout_status": "not_pristine; 2026-01-25/26 and 2026-03-16 used for gates/smoke",
        "recovery_window_software_fix": "retained; do not undo (six_zone_daily_controller ramp window)",
        "ramp_gate_frozen": {
            "engineering_margin": ENGINEERING_MARGIN,
            "threshold_f_per_15min": ramp.get("threshold_f_per_15min"),
            "incumbent_max": ramp.get("incumbent_simulated_max_f_per_15min"),
            "low_unocc_max": ramp.get("perturbed_simulated_max_f_per_15min"),
            "high_occ_max": ramp.get("high_occ_simulated_max_f_per_15min"),
            "passed": ramp.get("passed"),
            "verdict": ramp.get("verdict"),
            "source_artifact": "docs/audits/figures/postfix/ramp_gate.json",
        },
        "remaining_physics_finding": (
            "Evening DualSP 70→65 at occupancy_end causes ~4.6°F zone-air drop in 15 min; "
            "A04 has no ZoneCapacitanceMultiplier or InternalMass. SCH_HtgSP 03:15 is "
            "calendar 06:45 minus optimum_start_h=3.5, not a BAS occupancy start."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=None)
    args = p.parse_args()
    site = require_site_root(args.site_root)
    manifest = freeze_baseline(app=_APP, site=site)
    dest = _APP / "docs" / "audits" / "figures" / "a04v2" / "phase0" / "baseline_manifest.json"
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
