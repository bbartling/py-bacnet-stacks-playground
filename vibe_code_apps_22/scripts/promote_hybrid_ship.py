#!/usr/bin/env python
"""Run hybrid 96-step rollout and promote artifacts for desktop ship."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from hybrid_rollout import (  # noqa: E402
    CONTRACT_VERSION,
    HONESTY,
    HybridModels,
    load_joblib_model,
    make_fixture_contract,
    rollout_96,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifacts", type=Path, default=_ML / "artifacts")
    ap.add_argument("--desktop-artifacts", type=Path, default=_APP / "desktop" / "artifacts")
    args = ap.parse_args(argv)

    art = args.artifacts
    base_job = art / "real_baseline_15min_v1.joblib"
    delta_job = art / "eplus_delta_15min_v1.joblib"
    if not base_job.is_file() or not delta_job.is_file():
        raise FileNotFoundError(
            f"need {base_job.name} and {delta_job.name} — train components A/B first"
        )

    base_m, cols_b, _ = load_joblib_model(base_job)
    delta_m, cols_d, _ = load_joblib_model(delta_job)
    if cols_b != cols_d:
        # align to baseline feature list; delta must match
        raise ValueError("baseline/delta feature_cols mismatch — retrain with same FEATURE_COLS_15MIN_MT")

    base_card = json.loads((art / "real_baseline_15min_v1_model_card.json").read_text(encoding="utf-8"))
    delta_card = json.loads((art / "eplus_delta_15min_v1_model_card.json").read_text(encoding="utf-8"))

    models = HybridModels(baseline=base_m, delta=delta_m, feature_cols=cols_b)
    contract = make_fixture_contract()
    # prefer measured midnight from real store if available
    site_store = Path(
        __import__("os").environ.get(
            "LAKESIDE_SITE_ROOT",
            r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
        )
    ) / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    if site_store.is_file():
        import pandas as pd

        df = pd.read_parquet(site_store)
        winter = df[df["month"].isin([12, 1, 2])]
        day = winter.groupby("day").size()
        day = day[day >= 96].index
        if len(day):
            d0 = str(sorted(day)[len(day) // 2])
            sub = winter[winter["day"] == d0].sort_values("step_15")
            row0 = sub.iloc[0]
            contract["init"] = {
                "facility_kw": float(row0["facility_kw"]),
                "facility_kw_lag2": float(row0.get("facility_kw_lag2", row0["facility_kw"]) or row0["facility_kw"]),
                "oat_f": float(row0["oat_f"]),
                **{c: float(row0[c]) for c in [
                    "zone_temp_1F_A_f",
                    "zone_temp_1F_B_f",
                    "zone_temp_1F_C_f",
                    "zone_temp_1F_D_f",
                    "zone_temp_2F_A_f",
                    "zone_temp_2F_B_f",
                ]},
            }
            contract["calendar"]["month"] = int(row0["month"])
            contract["calendar"]["doy"] = int(row0["doy"])
            contract["calendar"]["is_weekend"] = float(row0["is_weekend"])
            contract["weather_forecast_96"]["oat_f"] = sub["oat_f"].tolist()[:96]
            if "rh_pct" in sub.columns:
                contract["weather_forecast_96"]["rh_pct"] = sub["rh_pct"].fillna(50).tolist()[:96]
            if "ghi" in sub.columns:
                contract["weather_forecast_96"]["ghi"] = sub["ghi"].fillna(0).tolist()[:96]
            contract["init_day"] = d0

    result = rollout_96(models, contract)
    result["champion_baseline"] = base_card.get("champion")
    result["champion_delta"] = delta_card.get("champion")
    result["baseline_cv"] = base_card.get("cv_teacher_forced")
    result["delta_cv"] = delta_card.get("cv_teacher_forced")
    result["honesty"] = HONESTY
    result["contract_version"] = CONTRACT_VERSION

    walk_path = art / "hybrid_dsm_96_v1_walk.json"
    fix_dir = art / "fixtures"
    fix_dir.mkdir(parents=True, exist_ok=True)
    walk_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_walk.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_init.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    desk = args.desktop_artifacts
    desk.mkdir(parents=True, exist_ok=True)
    shutil.copy2(walk_path, desk / "hybrid_dsm_96_v1_walk.json")

    # copy hybrid component artifacts into desktop
    for stem in ("real_baseline_15min_v1", "eplus_delta_15min_v1"):
        for suffix in (".onnx", ".joblib", "_feature_meta.json", "_model_card.json"):
            src = art / f"{stem}{suffix}"
            if src.is_file():
                shutil.copy2(src, desk / src.name)

    # ship meta pointer (not old kW-only stem)
    ship = {
        "ship_mode": "hybrid_96",
        "honesty": HONESTY,
        "contract_version": CONTRACT_VERSION,
        "walk_json": "hybrid_dsm_96_v1_walk.json",
        "baseline_stem": "real_baseline_15min_v1",
        "delta_stem": "eplus_delta_15min_v1",
        "champion_baseline": result.get("champion_baseline"),
        "champion_delta": result.get("champion_delta"),
        "summary": result.get("summary"),
    }
    (desk / "hybrid_ship_manifest.json").write_text(json.dumps(ship, indent=2), encoding="utf-8")
    (art / "hybrid_ship_manifest.json").write_text(json.dumps(ship, indent=2), encoding="utf-8")

    print(json.dumps({"walk": str(walk_path), "desktop": str(desk), "summary": result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
