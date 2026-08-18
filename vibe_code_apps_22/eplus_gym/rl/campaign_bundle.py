"""Authoritative campaign bundle. No FakeContinuityPlant. No silent forecasts."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.a04_identity import A04_IDF_NAME, is_canonical_a04_idf_filename
from eplus_gym.control_v2 import build_six_schedules_f, observed_bas_incumbent_params
from eplus_gym.rl.active_model import ActiveModelError, verify_active_model
from eplus_gym.rl.campaign_preflight import PERFECT_FORECAST, dates_are_contiguous
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.obs_v3 import PERFECT_EPISODE_FORECAST
from eplus_gym.rl.split_manifest import build_split_manifest
from eplus_gym.site_pins import resolve_site_epw, sha256_file

PUBLIC_LABELS = (
    "SIMULATION_ONLY_RL_RESEARCH",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO BACNET COMMAND AUTHORITY",
)


class CampaignBundleError(ValueError):
    """Campaign bundle could not be constructed."""


def _contiguous_or_raise(days: Sequence[str]) -> list[str]:
    out = [str(d)[:10] for d in days]
    if not out:
        raise CampaignBundleError("episode dates missing")
    if not dates_are_contiguous(out):
        raise CampaignBundleError("refusing randomly sampled isolated dates; episode days must be contiguous")
    return out


def refuse_a04_unless_explicit(*, idf_name: str, manifest: Mapping[str, Any]) -> None:
    if is_canonical_a04_idf_filename(idf_name) and not manifest.get("a04_explicitly_verified_active"):
        raise CampaignBundleError("campaign refuses A04 unless it is explicitly the verified active model")


def resolve_verified_trackb_idf(app_root: Path) -> tuple[Path, dict[str, Any]]:
    manifest = verify_active_model(app_root)
    rel = str(manifest.get("idf_path") or "")
    if not rel:
        raise ActiveModelError("champion idf_path missing")
    idf = Path(app_root) / rel
    refuse_a04_unless_explicit(idf_name=idf.name, manifest=manifest)
    got = sha256_file(idf)
    if got != str(manifest.get("idf_sha256")):
        raise ActiveModelError(f"champion IDF hash mismatch: {got}")
    return idf, manifest


def forecasts_from_epw(epw: Path, days: Sequence[str]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for day in days:
        fc = forecast_from_epw_replay(epw, day)
        if len(fc.temps_c) != 24:
            raise CampaignBundleError(f"EPW replay forecast for {day} is not 24 hourly values")
        out[str(day)[:10]] = list(fc.temps_c)
    return out


def _require_forecasts(days: Sequence[str], forecasts: Mapping[str, Sequence[float]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for day in days:
        series = forecasts.get(str(day)[:10])
        if not series or len(list(series)) != 24:
            raise CampaignBundleError(f"missing hourly forecasts for {day}; refusing silent synthesis")
        out[str(day)[:10]] = [float(x) for x in series]
    return out


def empty_bundle_template(*, days: Sequence[str]) -> dict[str, Any]:
    ds = _contiguous_or_raise(days)
    split = build_split_manifest(ds)
    return {
        "schema": "vibe22.campaign_bundle.v1",
        "public_labels": list(PUBLIC_LABELS),
        "days": ds,
        "forecast_source": PERFECT_EPISODE_FORECAST,
        "tariff_status": "ILLUSTRATIVE",
        "reward_contract_version": "reward_v2",
        "control_contract_version": "control_contract_v2",
        "observation_contract_version": "observation_contract_v3",
        "action_contract_version": "ppo_action_contract_v2",
        "split": split,
        "hourly_forecasts": {},
        "paired_baselines": {},
        "long_campaign_allowed_maps_to": "SIMULATION_TRAINING_READY",
    }


def provenance_baseline_record(
    payload: Mapping[str, Any],
    *,
    day: str,
    idf_sha256: str,
    epw_sha256: str,
    lookback_fp: str,
    baseline_fp: str,
) -> dict[str, Any]:
    rec = dict(payload)
    rec.update(
        {
            "day": str(day)[:10],
            "run_period": str(day)[:10],
            "idf_sha256": idf_sha256,
            "epw_sha256": epw_sha256,
            "energyplus_version": "26.1.0",
            "lookback_schedule_fingerprint": lookback_fp,
            "baseline_schedule_fingerprint": baseline_fp,
            "initial_state_id": rec.get("initial_state_id") or f"midnight_after_lookback:{day}",
            "trajectory_hash": rec.get("trajectory_hash") or trajectory_hash(rec),
            "n_intervals": int(rec.get("n_intervals") or len(rec.get("facility_kw") or [])),
            "TEST_DOUBLE": False,
        }
    )
    return rec


def prepare_campaign_bundle(
    *,
    app_root: Path,
    site_root: Path | None = None,
    days: Sequence[str],
    hourly_forecasts: Mapping[str, Sequence[float]] | None = None,
    paired_baselines: Mapping[str, Mapping[str, Any]] | None = None,
    idf: Path | None = None,
    epw: Path | None = None,
    manifest: Mapping[str, Any] | None = None,
    live_incumbent_baselines: bool = False,
    output_root: Path | None = None,
    opening_mtd_peak_kw: float | None = None,
) -> dict[str, Any]:
    """Build a hash-verified contiguous campaign bundle. Never synthesizes forecasts."""
    ds = _contiguous_or_raise(days)
    app_root = Path(app_root)
    body = empty_bundle_template(days=ds)
    if manifest is None:
        try:
            idf_path, manifest = resolve_verified_trackb_idf(app_root)
        except ActiveModelError as exc:
            raise CampaignBundleError(f"no active verified model: {exc}") from exc
        idf = idf_path
    else:
        manifest = dict(manifest)
        if idf is None:
            rel = str(manifest.get("idf_path") or "")
            if not rel:
                raise CampaignBundleError("no active verified model: champion idf_path missing")
            idf = Path(rel) if Path(rel).is_file() else app_root / rel
        refuse_a04_unless_explicit(idf_name=Path(idf).name, manifest=manifest)
    idf = Path(idf)
    if not idf.is_file():
        raise CampaignBundleError(f"champion IDF missing: {idf}")
    if epw is None:
        if site_root is None:
            raise CampaignBundleError("site_root required to resolve EPW")
        epw = resolve_site_epw(Path(site_root))
    epw = Path(epw)
    forecasts = dict(hourly_forecasts or {})
    if not forecasts:
        forecasts = forecasts_from_epw(epw, ds)
    forecasts = _require_forecasts(ds, forecasts)
    lookback_sched = build_six_schedules_f(observed_bas_incumbent_params())
    lookback_fp = schedule_fingerprint(lookback_sched)
    incumbent_fp = lookback_fp
    baselines: dict[str, Any] = {str(k)[:10]: dict(v) for k, v in (paired_baselines or {}).items()}
    if live_incumbent_baselines:
        if site_root is None:
            raise CampaignBundleError("site_root required for live incumbent baselines")
        from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant

        out = Path(output_root or (Path(site_root) / "reports" / "eplus_gym" / "rl" / "campaign_baselines"))
        plant = EnergyPlusContinuityPlant(
            site_root=Path(site_root),
            epw=epw,
            idf=idf,
            output=out / "incumbent",
            days=ds,
            lookback_schedules=lookback_sched,
        )
        plant.start_episode()
        try:
            for day in ds:
                payload = plant.simulate_day(lookback_sched, oat_c=forecasts[day])
                baselines[day] = provenance_baseline_record(
                    payload,
                    day=day,
                    idf_sha256=sha256_file(idf),
                    epw_sha256=sha256_file(epw),
                    lookback_fp=lookback_fp,
                    baseline_fp=incumbent_fp,
                )
        finally:
            plant.finish_quality()
    if any(day not in baselines for day in ds):
        raise CampaignBundleError("missing paired baseline artifacts; refusing candidate-as-baseline")
    first = date.fromisoformat(ds[0])
    opening_mtd = float(opening_mtd_peak_kw or 0.0)
    if first.day != 1 and opening_mtd_peak_kw is None:
        opening_mtd_note = "mid_month_block_opening_mtd_unpublished_do_not_pretend_zero"
    else:
        opening_mtd_note = "billing_month_start" if first.day == 1 else "explicit_opening_mtd"
    idf_sha = sha256_file(idf)
    epw_sha = sha256_file(epw)
    body.update(
        {
            "idf_path": str(idf),
            "idf_sha256": idf_sha,
            "verified_idf_sha256": idf_sha,
            "epw_path": str(epw),
            "epw_sha256": epw_sha,
            "verified_epw_sha256": epw_sha,
            "energyplus_version": "26.1.0",
            "hourly_forecasts": forecasts,
            "forecast_source": PERFECT_FORECAST,
            "paired_baselines": baselines,
            "lookback_schedule_fingerprint": lookback_fp,
            "incumbent_schedule_fingerprint": incumbent_fp,
            "initial_state_provenance": "continuity_plant_lookback_then_scored_days",
            "billing_init": {
                "opening_mtd_peak_kw": opening_mtd,
                "note": opening_mtd_note,
            },
            "model_id": manifest.get("model_id"),
            "active_model": dict(manifest),
            "refused_idf": A04_IDF_NAME,
        }
    )
    return body


def write_bundle(path: Path, bundle: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(bundle), indent=2) + "\n", encoding="utf-8")
    return path


def load_bundle(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
