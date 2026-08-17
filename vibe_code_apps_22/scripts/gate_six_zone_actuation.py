#!/usr/bin/env python3
"""Six-zone actuation perturbation gate (real EnergyPlus)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.episode import SCREENING_CLAIM, run_controller_episode  # noqa: E402
from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv  # noqa: E402
from eplus_gym.site_env import require_site_root  # noqa: E402
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file  # noqa: E402
from eplus_gym.six_zone_daily_controller import ACTION_KEYS  # noqa: E402
from eplus_gym.stage_idf import stage_idf_for_period  # noqa: E402


class ConstSixAction:
    def __init__(self, vals_f: list[float]):
        self.vals_c = np.asarray([(v - 32.0) * 5.0 / 9.0 for v in vals_f], dtype=np.float32)

    def action(self, step: int):
        return self.vals_c


def main() -> int:
    print(SCREENING_CLAIM)
    site = require_site_root(os.environ.get("SITE_ROOT"))
    day = "2026-01-26"
    try:
        idf, epw = resolve_a04_and_epw(site)
    except FileNotFoundError as exc:
        print(f"NO-GO: {exc}")
        return 2
    champ_hash = sha256_file(idf)
    out = site / "reports" / "eplus_gym" / "gates" / "six_zone_actuation"
    out.mkdir(parents=True, exist_ok=True)

    cases = {
        "global_70": [70.0] * 6,
        "only_1F_A_68": [68.0, 70.0, 70.0, 70.0, 70.0, 70.0],
        "only_2F_B_68": [70.0, 70.0, 70.0, 70.0, 70.0, 68.0],
    }
    results = {}
    for name, vals_f in cases.items():
        cdir = out / name
        cdir.mkdir(parents=True, exist_ok=True)
        staged = stage_idf_for_period(
            idf,
            cdir / f"staged_{idf.name}",
            day,
            day,
            site_root=site,
            six_zone_actuators=True,
        )
        ctrl = ConstSixAction(vals_f)

        def factory(staged_idf=staged, cdir=cdir):
            return LakesideW2AEnv(
                {
                    "epw": str(epw),
                    "idf": str(staged_idf),
                    "output": str(cdir / "eplus"),
                    "default_action_c": list(ctrl.vals_c),
                    "queue_timeout_s": 180.0,
                    "six_zone_actuators": True,
                }
            )

        ep = run_controller_episode(factory, ctrl, lookback_days=0, scored_day=day, max_steps=96)
        rows = ep["rows"]
        # Mean requested/applied per zone
        summary = {"requested_f": dict(zip(ACTION_KEYS, vals_f)), "n_rows": len(rows)}
        for i, key in enumerate(ACTION_KEYS):
            col = f"htg_sp_{key}_f"
            app = f"htg_sp_applied_{key}_f"
            if col in rows[0]:
                summary[f"mean_{col}"] = float(np.mean([r[col] for r in rows if col in r]))
            if rows and app in rows[0]:
                summary[f"mean_{app}"] = float(
                    np.nanmean([r.get(app, float("nan")) for r in rows])
                )
        results[name] = summary
        (cdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(name, json.dumps(summary))

    # Pass criteria
    def near(a, b, tol=0.6):
        return abs(float(a) - float(b)) < tol

    g = results["global_70"]
    a = results["only_1F_A_68"]
    b = results["only_2F_B_68"]
    issues = []
    # 1F_A case: 1F_A ~68, others ~70
    if not near(a.get("mean_htg_sp_1F_A_f", 0), 68.0):
        issues.append("1F_A case: 1F_A not ~68")
    for key in ACTION_KEYS:
        if key == "1F_A":
            continue
        if not near(a.get(f"mean_htg_sp_{key}_f", 0), 70.0):
            issues.append(f"1F_A case: {key} not ~70")
    if not near(b.get("mean_htg_sp_2F_B_f", 0), 68.0):
        issues.append("2F_B case: 2F_B not ~68")
    for key in ACTION_KEYS:
        if key == "2F_B":
            continue
        if not near(b.get(f"mean_htg_sp_{key}_f", 0), 70.0):
            issues.append(f"2F_B case: {key} not ~70")
    if sha256_file(idf) != champ_hash:
        issues.append("champion hash changed")

    report = {
        "scientific_claim": SCREENING_CLAIM,
        "ready": not issues,
        "issues": issues,
        "cases": results,
        "champion_sha256": champ_hash,
        "champion_unchanged": sha256_file(idf) == champ_hash,
        "action_keys": list(ACTION_KEYS),
    }
    (out / ("READY.json" if not issues else "NOGO.json")).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (out / "gate_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("READY" if not issues else "NO-GO", issues)
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
