"""Identical-state lookback → target-day ContinuityPlant runner."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import observed_bas_incumbent_params
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.nightly_grid_cost import score_candidate_day
from eplus_gym.rl.research_poc import refuse_fake_plant
from eplus_gym.rl.research_spaces import research_build_six_schedules_f
from eplus_gym.site_pins import resolve_site_epw, sha256_file


class IdenticalStateFailure(RuntimeError):
    """Midnight zone temperatures diverge across candidates."""


def prove_identical_midnight(
    zone_rows: Sequence[Sequence[float]],
    *,
    tol_f: float = 0.05,
) -> dict[str, Any]:
    if not zone_rows:
        raise IdenticalStateFailure("no midnight zone samples")
    ref = [float(x) for x in zone_rows[0]]
    max_delta = 0.0
    for row in zone_rows[1:]:
        vals = [float(x) for x in row]
        if len(vals) != 6 or len(ref) != 6:
            raise IdenticalStateFailure("need six zone temperatures")
        for a, b in zip(ref, vals):
            max_delta = max(max_delta, abs(a - b))
    ok = max_delta <= float(tol_f)
    out = {
        "ok": ok,
        "tol_f": float(tol_f),
        "max_abs_delta_f": max_delta,
        "reference_zone_temps_f": ref,
        "n_samples": len(zone_rows),
    }
    if not ok:
        raise IdenticalStateFailure(f"midnight zone delta {max_delta} > tol {tol_f}")
    return out


def run_identical_state_candidate(
    *,
    site: Path,
    app_root: Path,
    out_dir: Path,
    day: str,
    lookback_day: str,
    candidate_id: str,
    target_schedules: Mapping[str, Sequence[float]],
    baseline_payload: Mapping[str, Any],
    lookback_params=None,
    opening_mtd_kw: float = 0.0,
    tariff_mode: str = "FLAT_PLUS_DEMAND",
    queue_timeout_s: float = 600.0,
) -> dict[str, Any]:
    """One E+ process: identical lookback day + candidate target day; score target only."""
    epw = resolve_site_epw(site)
    idf = Path(app_root) / "models" / "eplus" / A04_IDF_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    lb_params = lookback_params or observed_bas_incumbent_params()
    lookback_sched = research_build_six_schedules_f(lb_params, lookback_day)
    oat = forecasts_from_epw(epw, [day])
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=idf,
        output=out_dir,
        days=[day],
        lookback_days=1,
        lookback_schedules=lookback_sched,
        queue_timeout_s=queue_timeout_s,
    )
    refuse_fake_plant(plant)
    t0 = time.perf_counter()
    plant.start_episode()
    # After lookback consumption inside start_episode, zone_temps_f are midnight state.
    midnight_zones = list(plant.zone_temps_f)
    payload = plant.simulate_day(dict(target_schedules), oat_c=list(oat[day]))
    quality = plant.finish_quality()
    fac = [float(x) for x in payload["facility_kw"]]
    if len(fac) != 96:
        raise ValueError(f"{candidate_id}: expected 96 intervals, got {len(fac)}")
    scored = score_candidate_day(
        day=day,
        candidate_facility_kw=fac,
        candidate_zone_temps_f=payload["zone_temps_series_f"],
        baseline_facility_kw=baseline_payload["facility_kw"],
        baseline_zone_temps_f=baseline_payload["zone_temps_series_f"],
        candidate_schedules=target_schedules,
        previous_schedules=lookback_sched,
        mtd_peak_kw=float(opening_mtd_kw),
        baseline_mtd_peak_kw=float(opening_mtd_kw),
        tariff_mode=tariff_mode,
    )
    severe = int((quality or {}).get("severe_count") or 0)
    fatal = int((quality or {}).get("fatal_count") or 0)
    if severe or fatal:
        raise RuntimeError(f"{candidate_id}: severe={severe} fatal={fatal}")
    result = {
        "candidate_id": candidate_id,
        "day": day,
        "lookback_day": lookback_day,
        "midnight_zone_temps_f": midnight_zones,
        "facility_kw": fac,
        "zone_temps_series_f": payload["zone_temps_series_f"],
        "n_intervals": 96,
        "n_process_starts": int(plant.n_process_starts),
        "schedule_fingerprint": schedule_fingerprint(target_schedules),
        "lookback_schedule_fingerprint": schedule_fingerprint(lookback_sched),
        "trajectory_sha256": trajectory_hash({"facility_kw": fac, "n_intervals": 96}),
        "quality": quality,
        "score": scored,
        "elapsed_s": time.perf_counter() - t0,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "weather_label": "RETROSPECTIVE_WEATHER_BENCHMARK",
        "exit_code": 0,
        "status": "OK",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_baseline_incumbent(
    *,
    site: Path,
    app_root: Path,
    out_dir: Path,
    day: str,
    lookback_day: str,
    opening_mtd_kw: float = 0.0,
    tariff_mode: str = "FLAT_PLUS_DEMAND",
) -> dict[str, Any]:
    params = observed_bas_incumbent_params()
    sched = research_build_six_schedules_f(params, day)
    # Self-paired bootstrap: run once to get trajectory, then score vs self for ledger baseline.
    # Selection uses paired baseline from this payload for all candidates.
    epw = resolve_site_epw(site)
    idf = Path(app_root) / "models" / "eplus" / A04_IDF_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    lookback_sched = research_build_six_schedules_f(params, lookback_day)
    oat = forecasts_from_epw(epw, [day])
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=idf,
        output=out_dir,
        days=[day],
        lookback_days=1,
        lookback_schedules=lookback_sched,
        queue_timeout_s=600.0,
    )
    refuse_fake_plant(plant)
    plant.start_episode()
    midnight = list(plant.zone_temps_f)
    payload = plant.simulate_day(sched, oat_c=list(oat[day]))
    quality = plant.finish_quality()
    fac = [float(x) for x in payload["facility_kw"]]
    compact = {
        "facility_kw": fac,
        "zone_temps_series_f": payload["zone_temps_series_f"],
        "peak_kw": float(payload["peak_kw"]),
        "daily_kwh": float(payload["daily_kwh"]),
        "trajectory_sha256": trajectory_hash({"facility_kw": fac, "n_intervals": 96}),
        "n_intervals": 96,
        "midnight_zone_temps_f": midnight,
        "quality": quality,
        "schedule_fingerprint": schedule_fingerprint(sched),
    }
    # Score vs self only to populate fields; real selection compares candidates to this baseline traj.
    score = score_candidate_day(
        day=day,
        candidate_facility_kw=fac,
        candidate_zone_temps_f=payload["zone_temps_series_f"],
        baseline_facility_kw=fac,
        baseline_zone_temps_f=payload["zone_temps_series_f"],
        candidate_schedules=sched,
        previous_schedules=lookback_sched,
        mtd_peak_kw=opening_mtd_kw,
        baseline_mtd_peak_kw=opening_mtd_kw,
        tariff_mode=tariff_mode,
    )
    compact["score"] = score
    compact["candidate_id"] = "observed_bas_incumbent_v2_baseline"
    (out_dir / "baseline.json").write_text(json.dumps(compact, indent=2), encoding="utf-8")
    return compact
