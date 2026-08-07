#!/usr/bin/env python
"""Run hybrid 96-step rollout and promote artifacts for desktop ship.

Prefer the sklearn notebook (Run All). CLI requires VIBE22_ALLOW_CLI_TRAIN=1.

Promote gates (Audit P0 + Wave 4):
- Baseline AND delta cards must include non-empty ``cv_recursive_96_heldout``
  with usable facility metrics (facility_kw_mae / mae_delta_kw).
- Held-out ``note``/``status`` must not carry provisional, teacher_forced, debug,
  in_sample, not_evaluated, or insufficient tokens.
- Usable both-arm pair count >= MIN_PAIRS (12), else refuse unless
  ``VIBE22_ALLOW_SMOKE_PROMOTE=1`` (which stamps the ship manifest with the
  ``UNDERPOWERED_SMOKE_FARM`` watermark and ship_mode=smoke_artifact).
- Multi-res monthly+hourly gates must pass (``eplus_multires_validation.json``)
  OR acceptance-policy ``hourly_gate_waiver.active`` must be true. Smoke promote
  never counts as operational even with waiver.
- ``delta_peak_kw > 0`` or ``delta_kwh > 500`` → outcome_flag REJECTED_DSM_OUTCOME.
- IdealLoads + fixed-COP disclaimer is always emitted.
- Transactional desktop switch: write candidate bundle → verify → atomic replace
  with rollback on failure.
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
SMOKE_WATERMARK = "UNDERPOWERED_SMOKE_FARM"
REJECTED_DSM_OUTCOME = "REJECTED_DSM_OUTCOME"
DELTA_KWH_REJECT_THRESHOLD = 500.0
POLICY_PATH = _APP / "contracts" / "eplus_dsm_acceptance_policy_v1.json"
# Notes / statuses that betray a non-honest held-out metric.
FORBIDDEN_NOTE_TOKENS = (
    "provisional",
    "teacher_forced",
    "debug",
    "in_sample",
    "not_evaluated",
    "insufficient",
)


def _promoted_via() -> str:
    return "cli" if os.environ.get("VIBE22_ALLOW_CLI_TRAIN") == "1" else "notebook"


def _load_acceptance_policy() -> dict[str, Any]:
    if not POLICY_PATH.is_file():
        return {}
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _multires_gate(*, is_smoke: bool) -> dict[str, Any]:
    """Require monthly+hourly pass, or explicit hourly waiver (never operational on smoke)."""
    policy = _load_acceptance_policy()
    waiver = (policy.get("waivers") or {}).get("hourly_gate_waiver") or {}
    waiver_active = bool(waiver.get("active"))
    candidates = [
        _APP / "desktop" / "artifacts" / "mvm" / "eplus_multires_validation.json",
        _ML / "artifacts" / "eplus_campaigns" / "latest_validation.json",
        Path(
            os.environ.get(
                "LAKESIDE_SITE_ROOT",
                r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
            )
        )
        / "reports"
        / "eplus"
        / "multires"
        / "eplus_multires_validation.json",
    ]
    doc = None
    path_used = None
    for p in candidates:
        if p.is_file():
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                path_used = str(p)
                break
            except json.JSONDecodeError:
                continue
    if doc is None:
        if is_smoke:
            return {
                "ok": True,
                "operational": False,
                "reason": "smoke_promote_without_multires_doc",
                "path": None,
            }
        raise ValueError(
            "Missing eplus_multires_validation.json — run scripts/validate_eplus_multires.py "
            "before operational promote (or use smoke env for screening only)."
        )
    overall = doc.get("overall") or {}
    monthly_ok = bool(overall.get("monthly_pass"))
    hourly_ok = bool(overall.get("hourly_pass"))
    if monthly_ok and hourly_ok:
        return {
            "ok": True,
            "operational": not is_smoke,
            "reason": None,
            "path": path_used,
            "waiver": False,
        }
    if monthly_ok and waiver_active and not is_smoke:
        return {
            "ok": True,
            "operational": False,
            "reason": f"hourly_waived:{waiver.get('reason')}",
            "path": path_used,
            "waiver": True,
            "note": "Waiver allows research promote only — operational DSM still prohibited",
        }
    if is_smoke:
        return {
            "ok": True,
            "operational": False,
            "reason": overall.get("blocker_reason") or "hourly_fail_smoke_ok",
            "path": path_used,
            "waiver": False,
        }
    raise ValueError(
        "Refuse operational promote: multi-res gates not met "
        f"(monthly_pass={monthly_ok}, hourly_pass={hourly_ok}, "
        f"blocker={overall.get('blocker_reason')}). "
        "Activate contracts/eplus_dsm_acceptance_policy_v1.json "
        "waivers.hourly_gate_waiver only with explicit approval, "
        "or keep VIBE22_ALLOW_SMOKE_PROMOTE=1 for screening."
    )


def _atomic_desktop_switch(candidate: Path, desk: Path) -> None:
    """Replace desktop artifacts from candidate dir; restore backup on failure."""
    backup = desk.parent / f"{desk.name}._promote_bak"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    if desk.exists():
        shutil.copytree(desk, backup)
    try:
        desk.mkdir(parents=True, exist_ok=True)
        for src in candidate.iterdir():
            dst = desk / src.name
            if src.is_file():
                shutil.copy2(src, dst)
    except Exception:
        if backup.exists():
            if desk.exists():
                shutil.rmtree(desk, ignore_errors=True)
            shutil.copytree(backup, desk)
        raise
    finally:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

def _find_forbidden_notes(obj: Any, path: str = "") -> list[str]:
    """Return locations where a ``note``/``status`` field holds a forbidden token."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{path}{k}"
            if isinstance(v, str) and str(k).lower() in ("note", "status"):
                low = v.lower()
                if any(tok in low for tok in FORBIDDEN_NOTE_TOKENS):
                    hits.append(f"{kp}={v!r}")
            hits.extend(_find_forbidden_notes(v, kp + "."))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            hits.extend(_find_forbidden_notes(x, f"{path}[{i}]."))
    return hits


def _reject_provisional_heldout(held: Any, arm: str) -> None:
    """Raise if a held-out block carries provisional / teacher-forced / etc notes."""
    hits = _find_forbidden_notes(held)
    if hits:
        raise ValueError(
            f"{arm} cv_recursive_96_heldout carries forbidden note/status "
            f"({', '.join(hits)}); regenerate honest held-out recursive CV via notebook"
        )


def _heldout_has_facility_metrics(held: Any) -> bool:
    """True if cv_recursive_96_heldout is a non-empty dict with facility MAE somewhere."""
    if not isinstance(held, dict) or not held:
        return False
    if held.get("note") == "insufficient_heldout_days":
        return False
    if held.get("status") == "not_evaluated":
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
        "facility_kw_cv_rmse",
        "facility_kw_nmbe",
        "zone_temp_mae_mean",
        "mae_delta_kw",
        "mae_delta_kw_peak",
        "mae_delta_temp_mean",
        "cv_rmse_delta_kw",
        "nmbe_delta_kw",
        "rmse_delta_kw",
        "n_heldout_days",
        "note",
    )
    return {k: src[k] for k in keys if isinstance(src, dict) and k in src}


G14_MONTHLY_REFERENCE = {
    "nmbe_abs_max": 0.05,
    "cv_rmse_max": 0.15,
    "note": (
        "ASHRAE Guideline 14 monthly calibrated reference (|NMBE|<=5%, CV(RMSE)<=15%); "
        "hybrid 15-min held-out metrics are screening only, not a monthly G14 compliance claim"
    ),
}


def _build_mv_precision(
    *,
    champion_baseline: Any,
    champion_delta: Any,
    baseline_held: dict[str, Any],
    delta_held: dict[str, Any],
) -> dict[str, Any]:
    """Display block for desktop: G14 primary, MAE secondary, screening +/- kW."""
    peak = baseline_held.get("facility_kw_mae_peak_05_09")
    mae = baseline_held.get("facility_kw_mae")
    precision_pm = peak if peak is not None else mae
    return {
        "primary": ["nmbe", "cv_rmse"],
        "secondary": ["mae", "rmse", "mae_peak_05_09"],
        "precision_pm_kw": float(precision_pm) if precision_pm is not None else None,
        "precision_label": "screening +/- kW from held-out morning-peak MAE (not a CI)",
        "g14_monthly_reference": dict(G14_MONTHLY_REFERENCE),
        "champion_baseline": champion_baseline,
        "champion_delta": champion_delta,
        "baseline": {
            "nmbe": baseline_held.get("facility_kw_nmbe"),
            "cv_rmse": baseline_held.get("facility_kw_cv_rmse"),
            "mae": baseline_held.get("facility_kw_mae"),
            "rmse": baseline_held.get("facility_kw_rmse"),
            "mae_peak_05_09": baseline_held.get("facility_kw_mae_peak_05_09"),
            "zone_temp_mae_mean": baseline_held.get("zone_temp_mae_mean"),
            "n_heldout_days": baseline_held.get("n_heldout_days"),
        },
        "delta": {
            "nmbe": delta_held.get("nmbe_delta_kw"),
            "cv_rmse": delta_held.get("cv_rmse_delta_kw"),
            "mae": delta_held.get("mae_delta_kw"),
            "rmse": delta_held.get("rmse_delta_kw"),
            "mae_peak_05_09": delta_held.get("mae_delta_kw_peak"),
            "n_heldout_days": delta_held.get("n_heldout_days"),
        },
    }


def _stamp_feature_meta_precision(
    art: Path,
    desk: Path,
    *,
    stem: str,
    precision_pm_kw: float | None,
    champion: Any,
    honesty: str,
) -> None:
    """Write precision_pm_kw + champion into feature_meta for Rust ONNX load path."""
    for root in (art, desk):
        meta_path = root / f"{stem}_feature_meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if precision_pm_kw is not None:
            meta["precision_pm_kw"] = float(precision_pm_kw)
        if champion is not None:
            meta["champion"] = champion
        meta["honesty"] = honesty
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


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

    # --- Honesty gate: baseline held-out recursive CV ---
    base_held = base_card.get("cv_recursive_96_heldout")
    _reject_provisional_heldout(base_held, "baseline")
    if not _heldout_has_facility_metrics(base_held):
        raise ValueError(
            "baseline model card missing usable cv_recursive_96_heldout "
            "(need non-empty dict with facility_kw_mae / family metrics). "
            "Retrain component A via sklearn notebook so held-out recursive CV is recorded."
        )

    # --- Honesty gate: delta held-out recursive CV (real recursive, never TF copy) ---
    delta_held = delta_card.get("cv_recursive_96_heldout")
    _reject_provisional_heldout(delta_held, "delta")
    if not _heldout_has_facility_metrics(delta_held):
        raise ValueError(
            "delta model card missing usable cv_recursive_96_heldout "
            "(need non-empty dict with mae_delta_kw / facility_kw_mae). "
            "Retrain component B via sklearn notebook so held-out recursive CV is recorded."
        )

    # --- Coverage gate: usable both-arm pairs ---
    pair_count = _count_both_arm_pairs(art, delta_card)
    allow_smoke = os.environ.get(SMOKE_ENV) == "1"
    is_smoke = False
    if pair_count < MIN_PAIRS:
        if not allow_smoke:
            raise ValueError(
                f"usable both-arm pairs={pair_count} < MIN_PAIRS={MIN_PAIRS}. "
                f"Refuse promote unless {SMOKE_ENV}=1 (smoke/dev only). "
                "Grow the paired E+ farm or set the env explicitly."
            )
        is_smoke = True

    multires = _multires_gate(is_smoke=is_smoke)

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
            kw0 = float(row0["facility_kw"])
            # NaN is truthy in Python — never use ``nan or fallback``.
            lag2_raw = row0["facility_kw_lag2"] if "facility_kw_lag2" in row0.index else kw0
            try:
                lag2 = float(lag2_raw)
            except (TypeError, ValueError):
                lag2 = kw0
            if lag2 != lag2:  # NaN
                lag2 = kw0
            contract["init"] = {
                "facility_kw": kw0,
                "facility_kw_lag2": lag2,
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
            oat = pd.to_numeric(sub["oat_f"], errors="coerce")
            contract["weather_forecast_96"]["oat_f"] = oat.ffill().bfill().fillna(20.0).tolist()[:96]
            if "rh_pct" in sub.columns:
                rh = pd.to_numeric(sub["rh_pct"], errors="coerce")
                contract["weather_forecast_96"]["rh_pct"] = rh.fillna(50.0).tolist()[:96]
            if "ghi" in sub.columns:
                ghi = pd.to_numeric(sub["ghi"], errors="coerce")
                contract["weather_forecast_96"]["ghi"] = ghi.fillna(0.0).tolist()[:96]
            contract["init_day"] = d0

    result = rollout_96(models, contract)
    result["champion_baseline"] = base_card.get("champion")
    result["champion_delta"] = delta_card.get("champion")
    result["baseline_cv"] = base_card.get("cv_teacher_forced")
    result["delta_cv"] = delta_card.get("cv_teacher_forced")
    result["baseline_cv_recursive_96_heldout"] = _heldout_headlines(base_card)
    result["delta_cv_recursive_96_heldout"] = _heldout_headlines(delta_card)
    mv_precision = _build_mv_precision(
        champion_baseline=result.get("champion_baseline"),
        champion_delta=result.get("champion_delta"),
        baseline_held=result["baseline_cv_recursive_96_heldout"],
        delta_held=result["delta_cv_recursive_96_heldout"],
    )
    result["mv_precision"] = mv_precision
    result["honesty"] = HONESTY
    result["contract_version"] = CONTRACT_VERSION
    result["promoted_via"] = _promoted_via()
    result["pair_count"] = pair_count
    result["idealloads_cop_disclaimer"] = IDEALLOADS_COP_DISCLAIMER
    result["multires_gate"] = multires
    result["operational_dsm"] = bool(multires.get("operational"))

    ship_mode = "hybrid_96"
    if is_smoke:
        ship_mode = "smoke_artifact"
        result["watermark"] = SMOKE_WATERMARK
        result["ship_mode"] = ship_mode
        result["honesty_note"] = (
            f"{SMOKE_WATERMARK}: usable both-arm pairs={pair_count} < {MIN_PAIRS}; "
            "screening-only smoke artifact, not a client-grade result"
        )
    elif not multires.get("operational"):
        ship_mode = "research_artifact"
        result["ship_mode"] = ship_mode
        result["honesty_note"] = (
            multires.get("note")
            or multires.get("reason")
            or "multi-res gates incomplete — research promote only"
        )

    summary = result.get("summary") or {}
    delta_peak = float(summary.get("delta_peak_kw") or 0.0)
    delta_kwh = float(summary.get("delta_kwh") or 0.0)
    if delta_peak > 0 or delta_kwh > DELTA_KWH_REJECT_THRESHOLD:
        result["outcome_flag"] = REJECTED_DSM_OUTCOME

    walk_path = art / "hybrid_dsm_96_v1_walk.json"
    fix_dir = art / "fixtures"
    fix_dir.mkdir(parents=True, exist_ok=True)
    walk_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_walk.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (fix_dir / "hybrid_dsm_96_v1_init.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    # Candidate bundle → verify → atomic desktop switch
    cand = art / "_promote_candidate"
    if cand.exists():
        shutil.rmtree(cand, ignore_errors=True)
    cand.mkdir(parents=True)
    shutil.copy2(walk_path, cand / "hybrid_dsm_96_v1_walk.json")
    for stem in ("real_baseline_15min_v1", "eplus_delta_15min_v1"):
        for suffix in (".onnx", ".joblib", "_feature_meta.json", "_model_card.json"):
            src = art / f"{stem}{suffix}"
            if src.is_file():
                shutil.copy2(src, cand / src.name)
    # Gate check on candidate presence (joblib required; onnx optional for unit tests)
    for req in ("hybrid_dsm_96_v1_walk.json", "real_baseline_15min_v1.joblib", "eplus_delta_15min_v1.joblib"):
        if not (cand / req).is_file():
            shutil.rmtree(cand, ignore_errors=True)
            raise FileNotFoundError(f"promote candidate missing required {req}")
    _atomic_desktop_switch(cand, desk)
    shutil.rmtree(cand, ignore_errors=True)

    for stem in ("real_baseline_15min_v1", "eplus_delta_15min_v1"):
        for suffix in (".onnx", ".joblib", "_feature_meta.json", "_model_card.json"):
            src = art / f"{stem}{suffix}"
            if src.is_file():
                shutil.copy2(src, desk / src.name)

    pm = mv_precision.get("precision_pm_kw")
    _stamp_feature_meta_precision(
        art,
        desk,
        stem="real_baseline_15min_v1",
        precision_pm_kw=pm,
        champion=result.get("champion_baseline"),
        honesty=HONESTY,
    )
    _stamp_feature_meta_precision(
        art,
        desk,
        stem="eplus_delta_15min_v1",
        precision_pm_kw=pm,
        champion=result.get("champion_delta"),
        honesty=HONESTY,
    )

    ship = {
        "ship_mode": ship_mode,
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
        "mv_precision": mv_precision,
        "promoted_via": _promoted_via(),
        "multires_gate": multires,
        "operational_dsm": bool(multires.get("operational")),
    }
    if is_smoke:
        ship["watermark"] = SMOKE_WATERMARK
        ship["honesty_note"] = result.get("honesty_note")
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
