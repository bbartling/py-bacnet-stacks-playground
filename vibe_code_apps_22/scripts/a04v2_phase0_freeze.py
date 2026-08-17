"""Immutable A04 baseline freeze for A04-v2 transient work (Phase 0)."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
A04_NAME = "lakeside_w2a_a04_dual_champion.idf"
A04_SHA_PIN = "212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683"
ENGINEERING_MARGIN = 3.0


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    site = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")
    idf = _APP / "models" / "eplus" / A04_NAME
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    ramp = json.loads((_APP / "docs" / "audits" / "figures" / "postfix" / "ramp_gate.json").read_text(encoding="utf-8"))
    idf_sha = sha256_file(idf)
    if idf_sha != A04_SHA_PIN:
        raise SystemExit(f"A04 hash mismatch: {idf_sha}")
    out_dir = _APP / "docs" / "audits" / "figures" / "a04v2" / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Immutable copy reference (do not mutate source)
    copy_path = out_dir / f"IMMUTABLE_{A04_NAME}"
    if not copy_path.is_file() or sha256_file(copy_path) != idf_sha:
        copy_path.write_bytes(idf.read_bytes())

    git_sha = Path(_APP).resolve().parents[1]
    # worktree root is parents[1] from vibe_code_apps_22
    import subprocess

    repo = _APP.parent
    g = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    head = (g.stdout or "").strip()

    manifest = {
        "schema": "vibe22.a04v2.phase0_baseline.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": head,
        "branch_note": "stacked on PR #97 tip a5f6e770 (includes #96); #96/#97 still OPEN on develop",
        "a04": {
            "filename": A04_NAME,
            "sha256": idf_sha,
            "immutable_copy": str(copy_path.relative_to(_APP)).replace("\\", "/"),
            "role": "immutable_parent_comparison_baseline",
        },
        "epw": {
            "path": str(epw),
            "sha256": sha256_file(epw) if epw.is_file() else None,
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
            "A04 has no ZoneCapacitanceMultiplier or InternalMass."
        ),
    }
    dest = out_dir / "baseline_manifest.json"
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
