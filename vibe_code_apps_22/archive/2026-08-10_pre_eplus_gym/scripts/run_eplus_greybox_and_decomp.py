#!/usr/bin/env python
"""Run residual decomposition + grey-box translator bakeoff on aligned hourly."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
for p in (_APP, _APP / "ml", _APP / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lakeside.paths import site_root  # noqa: E402
from eplus_greybox_plant_translator import write_greybox_report  # noqa: E402
from eplus_residual_decomposition import write_residual_decomposition  # noqa: E402
from eplus_validation_contract import build_hourly_and_15min, utility_monthly_from_trial_sim  # noqa: E402
from eplus_calibrate_multires import _score_sim  # noqa: E402


def main() -> int:
    root = site_root()
    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    out = root / "reports" / "eplus" / "multires"
    out.mkdir(parents=True, exist_ok=True)

    products = build_hourly_and_15min(root, sim)
    aligned = products["hourly"]
    decomp = write_residual_decomposition(aligned, out / "decomposition")
    grey = write_greybox_report(aligned, out / "greybox")
    raw = _score_sim(root, sim, include_locked_holdout=False)

    comparison = {
        "operational_dsm_readiness": "NO-GO",
        "product_claim": "DIAGNOSTIC_ONLY",
        "families": {
            "RAW_EPLUS_IDEALLOADS_FIXED_COP": {
                "utility": {
                    "nmbe_pct": (raw.get("monthly_utility") or {}).get("nmbe_pct"),
                    "cvrmse_pct": (raw.get("monthly_utility") or {}).get("cvrmse_pct"),
                    "status": (raw.get("monthly_utility") or {}).get("status"),
                },
                "chrono_val_hourly": raw.get("hourly_chronological_validation"),
                "note": "locked winter evaluated only via champion holdout report",
            },
            "EPLUS_PROXY_CORRECTOR_DIAGNOSTIC": {
                "champion": grey.get("champion"),
                "product_claim": grey.get("product_claim"),
                "chrono_val_leaderboard": grey.get("leaderboard_chrono_val"),
                "locked_winter_holdout": grey.get("locked_winter_holdout"),
                "post_holdout_generalization": grey.get("post_holdout_generalization"),
            },
            "RAW_EPLUS_PHYSICAL_HP_PLANT": {
                "status": "design_only",
                "doc": "docs/superpowers/specs/2026-08-08-track-b-physical-hp-plant-design.md",
            },
            "REAL_DATA_ML": {"status": "see ship/farm artifacts — not recomputed here"},
            "NEAREST_DAY": {"status": "see nearest-day benchmark artifacts"},
        },
        "residual_decomposition": decomp.get("summary"),
    }
    (out / "model_family_comparison.json").write_text(
        json.dumps(comparison, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(comparison, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
