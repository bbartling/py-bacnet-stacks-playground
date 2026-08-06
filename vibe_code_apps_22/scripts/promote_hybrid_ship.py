#!/usr/bin/env python
"""Run hybrid 96-step rollout and promote artifacts for desktop ship.

Prefer the sklearn notebook (Run All). CLI requires VIBE22_ALLOW_CLI_TRAIN=1.

Promote gates (Audit P0):
- Baseline card must include non-empty ``cv_recursive_96_heldout`` with facility metrics.
- Usable both-arm pair count >= MIN_PAIRS (12), else refuse unless
  ``VIBE22_ALLOW_SMOKE_PROMOTE=1``.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

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

MIN_PAIRS = 12
IDEALLOADS_COP_DISCLAIMER = (
    "IdealLoads + fixed COP ≠ GSHP/GLHE plant; hybrid screening only."
)
SMOKE_ENV = "VIBE22_ALLOW_SMOKE_PROMOTE"


def _heldout_has_facility_metrics(held: Any) -> bool:
    """True if cv_recursive_96_heldout is a non-empty dict with facility MAE somewhere."""
    if not isinstance(held, dict) or not held:
        return False
    if held.get("note") == "insufficient_heldout_days":
        return False
    # champion-level flat metrics
    if "facility_kw_mae" in held and held["facility_kw_mae"] is not None:
        return True
    if "mae_delta_kw" in held and held["mae_delta_kw"] is not None:
        return True
    # by-family
    for v in held.values():
        if isinstance(v, dict) and (
            v.get("facility_kw_mae") is not None or v.get("mae_delta_kw") is not None
        ):
            return True
    return False


def _count_both_arm_pairs(art: Path, delta_card: dict[str, Any]) -> int:
    """Count usable both-arm pair_ids from paired parquet, else card/summary fallbacks."""
    paired = art / "heating_dsm_eplus_paired_15min_v1.parquet"
    if paired.is_file():
        import pandas as pd

        df = pd.read_parquet(paired, columns=["pair_id", "arm"])
        counts = df.groupby("pair_id")["arm"].nunique()
        return int((counts >= 2).sum())

    summary_path = art / "heating_dsm_eplus_paired_15min_v1_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for key in ("n_pair_ids", "n_pairs", "n_usable_pairs"):
            if key in summary:
                return int(summary[key])

    if "n_days" in delta_card and delta_card["n_days"] is not None:
        return int(delta_card["n_days"])
    return 0


def _heldout_headlines(card: dict[str, Any]) -> dict[str, Any]:
    held = card.get("cv_recursive_96_heldout") or {}
    if not isinstance(held, dict):
        return {}
    # Prefer champion family if present
    champ = card.get("champion")
    if champ and isinstance(held.get(champ), dict):
        src = held[champ]
    else:
        # first family dict with facility metrics, else flat
        src = held
        for v in held.values():
            if isinstance(v, dict) and (
                "facility_kw_mae" in v or "mae_delta_kw" in v
            ):
                src = v
                break
    keys = (
        "facility_kw_mae",
        "facility_kw_mae_peak_05_09",
        "facility_kw_rmse",
        "zone_temp_mae_mean",
        "mae_delta_kw",
        "mae_delta_kw_peak",
        "mae_delta_temp_mean",
        "n_heldout_days",
        "note",
    )
    return {k: src[k] for k in keys if isinstance(src, dict) and k in src}


def promote_hybrid(
    *,
    artifacts: Path | None = None,
    desktop_artifacts: Path | None = None,
) -> dict[str, Any]:
    """Build hybrid walk + copy ship artifacts. Callable from notebooks."""
    art = Path(artifacts or (_ML / "artifacts"))
    desk = Path(desktop_artifacts or (_APP / "desktop" / "artifacts"))

    base_job = art / "real_baseline_15min_v1.joblib"
    delta_job = art / "eplus_delta_15min_v1.joblib"
    if not base_job.is_file() or not delta_job.is_file():
        raise FileNotFoundError(
            f"need {base_job.name} and {delta_job.name} — train A/B via sklearn notebook first"
        )

    base_m, cols_b, _ = load_joblib_model(base_job)
    delta_m, cols_d, _ = load_joblib_model(delta_job)
    if cols_b != cols_d:
        raise ValueError("baseline/delta feature_cols mismatch — retrain with same FEATURE_COLS_15MIN_MT")

    base_card = json.loads((art / "real_baseline_15min_v1_model_card.json").read_text(encoding="utf-8"))
    delta_card = json.loads((art / "eplus_delta_15min_v1_model_card.json").read_text(encoding="utf-8"))

    held = base_card.get("cv_recursive_96_heldout")
    if not _heldout_has_facility_metrics(held):
        raise ValueError(
            "baseline model card missing usable cv_recursive_96_heldout "
            "(need non-empty dict with facility_kw_mae / family metrics). "
            "Retrain component A via sklearn notebook so held-out recursive CV is recorded."
        )

    pair_count = _count_both_arm_pairs(art, delta_card)
    allow_smoke = os.environ.get(SMOKE_ENV) == "1"
    if pair_count < MIN_PAIRS and not allow_smoke:
        raise ValueError(
            f"usable both-arm pairs={pair_count} < MIN_PAIRS={MIN_PAIRS}. "
            f"Refuse promote unless {SMOKE_ENV}=1 (smoke/dev only). "
            "Grow the paired E+ farm or set the env explicitly."
        )

    models = HybridModels(baseline=base_m, delta=delta_m, feature_cols=cols_b)
    contract = make_fixture_contract()
    site_store = Path(
        os.environ.get(
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
                "facility_kw_lag2": float(
                    row0.get("facility_kw_lag2", row0["facility_kw"]) or row0["facility_kw"]
                ),
                "oat_f": float(row0["oat_f"]),
                **{
                    c: float(row0[c])
                    for c in [
                        "zone_temp_1F_A_f",
                        "zone_temp_1F_B_f",
                        "zone_temp_1F_C_f",
                        "zone_temp_1F_D_f",
                        "zone_temp_2F_A_f",
                        "zone_temp_2F_B_f",
                    ]
                },
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
    result["baseline_cv_recursive_96_heldout"] = _heldout_headlines(base_card)
    result["delta_cv_recursive_96_heldout"] = _heldout_headlines(delta_card)
    result["honesty"] = HONESTY
    result["contract_version"] = CONTRACT_VERSION
    result["promoted_via"] = "notebook"
    result["pair_count"] = pair_count
    result["idealloads_cop_disclaimer"] = IDEALLOADS_COP_DISCLAIMER

    delta_peak = float((result.get("summary") or {}).get("delta_peak_kw") or 0.0)
    if delta_peak > 0:
        result["outcome_flag"] = "DSM_WORSENS_PEAK"

    walk_path = art / "hybrid_dsm_96_v1_walk.json"
    fix_dir = art / "fixtures"
    fix_dir.mkdir(parents=True, exist_ok=True)
    walk_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_walk.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_init.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    desk.mkdir(parents=True, exist_ok=True)
    shutil.copy2(walk_path, desk / "hybrid_dsm_96_v1_walk.json")

    for stem in ("real_baseline_15min_v1", "eplus_delta_15min_v1"):
        for suffix in (".onnx", ".joblib", "_feature_meta.json", "_model_card.json"):
            src = art / f"{stem}{suffix}"
            if src.is_file():
                shutil.copy2(src, desk / src.name)

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
        "pair_count": pair_count,
        "idealloads_cop_disclaimer": IDEALLOADS_COP_DISCLAIMER,
        "baseline_cv_recursive_96_heldout": result.get("baseline_cv_recursive_96_heldout"),
        "delta_cv_recursive_96_heldout": result.get("delta_cv_recursive_96_heldout"),
        "promoted_via": "notebook",
    }
    if result.get("outcome_flag"):
        ship["outcome_flag"] = result["outcome_flag"]
    (desk / "hybrid_ship_manifest.json").write_text(json.dumps(ship, indent=2), encoding="utf-8")
    (art / "hybrid_ship_manifest.json").write_text(json.dumps(ship, indent=2), encoding="utf-8")
    return {"walk": walk_path, "desktop": desk, "summary": result["summary"], "result": result}


def main(argv: list[str] | None = None) -> int:
    from notebook_gate import cli_train_allowed, refuse_cli_train

    if not cli_train_allowed():
        return refuse_cli_train("hybrid promote / 96-step walk")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifacts", type=Path, default=_ML / "artifacts")
    ap.add_argument("--desktop-artifacts", type=Path, default=_APP / "desktop" / "artifacts")
    args = ap.parse_args(argv)

    out = promote_hybrid(artifacts=args.artifacts, desktop_artifacts=args.desktop_artifacts)
    print(
        json.dumps(
            {"walk": str(out["walk"]), "desktop": str(out["desktop"]), "summary": out["summary"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
