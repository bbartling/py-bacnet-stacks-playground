"""LIVE 3-day EnergyPlusContinuityPlant proof on immutable A04. Not FakeContinuityPlant."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import (
    build_six_schedules_f,
    chronological_days,
    continuous_params,
    deep_setback_params,
    observed_bas_incumbent_params,
)
from eplus_gym.eplus_err import parse_eplus_err, scored_runtime_w2a_count
from eplus_gym.path_sanitize import redact_obj
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.multiday_env import assert_live_campaign_plant
from eplus_gym.rl.midnight_forecast import hourly_drybulb_from_epw
from eplus_gym.rl.reward_v2 import score_day_v2
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file
from eplus_gym.trackb_banks import scored_runtime_w2a_pass

ARMS = {
    "continuous_70": continuous_params(70.0),
    "observed_bas_incumbent": observed_bas_incumbent_params(),
    "deep_setback": deep_setback_params(),
}
BASELINE_ARM = "continuous_70"


def _sha_json(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def _plot_scorecard(path: Path, table: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    days = [r["day"] for r in table]
    x = np.arange(len(days))
    width = 0.25
    for i, arm in enumerate(("continuous_70", "observed_bas_incumbent", "deep_setback")):
        ys = [r["arms"][arm]["daily_kwh"] for r in table]
        ax.bar(x + (i - 1) * width, ys, width, label=arm.replace("_", " "))
    ax.set_xticks(x)
    ax.set_xticklabels(days)
    ax.set_ylabel("kWh")
    ax.set_title("A04 3-day LIVE continuity — screening only")
    ax.legend(fontsize=7)
    fig.text(0.01, 0.01, "Not operational. FakeContinuityPlant is not physics evidence.", fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run_arm(*, plant_kw: dict, arm_name: str, days: list[str], oat: dict[str, list[float]], site_out: Path) -> dict:
    params = ARMS[arm_name]
    schedules = build_six_schedules_f(params)
    plant = EnergyPlusContinuityPlant(**plant_kw)
    assert_live_campaign_plant(plant)
    plant.start_episode()
    payloads = {}
    midnight = []
    for day in days:
        payload = plant.simulate_day(schedules, oat_c=oat[day])
        payloads[day] = payload
        midnight.append({"day": day, "zone_temps_f": list(payload["zone_temps_f"]), "n_process_starts": payload["n_process_starts"]})
    quality = plant.finish_quality()
    arm_dir = site_out / arm_name
    arm_dir.mkdir(parents=True, exist_ok=True)
    compact = {
        "arm": arm_name,
        "live_energyplus": True,
        "n_process_starts": plant.n_process_starts,
        "n_days": plant.n_days,
        "continuous_conditioning": params.continuous_conditioning,
        "mode_label": params.mode_label(),
        "midnight": midnight,
        "days": {
            d: {
                "peak_kw": payloads[d]["peak_kw"],
                "daily_kwh": payloads[d]["daily_kwh"],
                "n_intervals": payloads[d]["n_intervals"],
                "facility_kw": payloads[d]["facility_kw"],
                "zone_temps_series_f": payloads[d]["zone_temps_series_f"],
            }
            for d in days
        },
        "eplus_quality": quality,
        "scored_runtime_w2a": scored_runtime_w2a_count(quality),
        "scored_runtime_w2a_pass": scored_runtime_w2a_pass(quality),
    }
    (arm_dir / "arm.json").write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    if plant.n_process_starts != 1:
        raise SystemExit(f"{arm_name} process starts={plant.n_process_starts}, expected 1")
    return compact


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="")
    p.add_argument("--start-day", default="2026-01-12")
    p.add_argument("--n-days", type=int, default=3)
    p.add_argument("--lookback-days", type=int, default=1)
    args = p.parse_args()
    site = require_site_root(args.site_root or None)
    idf, epw = resolve_a04_and_epw(site)
    if Path(idf).name != A04_IDF_NAME:
        raise SystemExit(f"multi-day continuity gallery uses immutable A04, got {Path(idf).name}")
    days = chronological_days(args.start_day, args.n_days)
    oat = {d: hourly_drybulb_from_epw(epw, __import__("datetime").date.fromisoformat(d)) for d in days}
    git_out = _APP / "docs" / "audits" / "figures" / "vibe22_repair" / "a04_multiday_continuity"
    git_out.mkdir(parents=True, exist_ok=True)
    site_out = site / "reports" / "eplus_gym" / "a04_multiday_continuity"
    site_out.mkdir(parents=True, exist_ok=True)
    plant_kw = dict(
        site_root=site,
        epw=epw,
        idf=idf,
        lookback_days=args.lookback_days,
        days=days,
        lookback_schedules=build_six_schedules_f(continuous_params(70.0)),
    )
    arms = {}
    n_live = 0
    for name in ARMS:
        n_live += 1
        arms[name] = run_arm(
            plant_kw={**plant_kw, "output": site_out / name / "process"},
            arm_name=name,
            days=days,
            oat=oat,
            site_out=site_out,
        )
    table = []
    for day in days:
        base = arms[BASELINE_ARM]["days"][day]
        row_arms = {}
        for name, payload in arms.items():
            cand = payload["days"][day]
            scored = score_day_v2(
                day=day,
                candidate_facility_kw=cand["facility_kw"],
                candidate_zone_temps_f=cand["zone_temps_series_f"],
                baseline_facility_kw=base["facility_kw"],
                baseline_zone_temps_f=base["zone_temps_series_f"],
                candidate_schedules=build_six_schedules_f(ARMS[name]),
                paycheck_k=2.0,
            )
            row_arms[name] = {
                "daily_kwh": scored.candidate["daily_kwh"],
                "day_peak_kw": scored.candidate["day_peak_kw"],
                "energy_cost": scored.candidate["energy_cost"],
                "demand_increment": scored.candidate["demand_increment"],
                "daily_cost": scored.candidate["daily_cost"],
                "savings_vs_continuous_70": scored.savings,
                "display_paycheck_usd": scored.display_paycheck_usd,
                "training_reward": scored.training_reward,
                "readiness_ok": scored.readiness["readiness_ok"],
            }
        table.append({"day": day, "arms": row_arms})
    starts = {n: arms[n]["n_process_starts"] for n in arms}
    midnight_ok = all(
        arms[n]["midnight"][i]["n_process_starts"] == 1 for n in arms for i in range(len(days))
    )
    manifest = {
        "schema": "vibe22.a04.multiday_continuity.v1",
        "scientific_claim": "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "idf": A04_IDF_NAME,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "days": days,
        "lookback_days": args.lookback_days,
        "live_energyplus": True,
        "fake_continuity_plant_is_physics_evidence": False,
        "n_live_energyplus_processes": n_live,
        "n_process_starts_by_arm": starts,
        "midnight_thermal_continuity_one_process": midnight_ok,
        "utility_table": table,
        "w2a_runtime_gate": {n: {"count": arms[n]["scored_runtime_w2a"], "pass": arms[n]["scored_runtime_w2a_pass"]} for n in arms},
        "long_campaign_allowed": False,
        "champion": None,
        "site_payload": "SITE_ROOT/reports/eplus_gym/a04_multiday_continuity",
    }
    (git_out / "manifest.json").write_text(json.dumps(redact_obj(manifest), indent=2) + "\n", encoding="utf-8")
    (site_out / "manifest.json").write_text(json.dumps(redact_obj(manifest), indent=2) + "\n", encoding="utf-8")
    _plot_scorecard(git_out / "kwh_scorecard.png", table)
    print(json.dumps({"n_live_energyplus_processes": n_live, "starts": starts, "days": days}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
