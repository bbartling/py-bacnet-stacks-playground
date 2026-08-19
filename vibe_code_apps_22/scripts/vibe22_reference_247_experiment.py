"""24/7 reference experiment — publication figure for continuous thermostatic conditioning.

NOT an operational baseline. Uses A04 parent (research fallback until hp67 v2 passes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import ACTION_KEYS
from eplus_gym.mega.compact_scorecard import build_compact_scorecard, idf_byte_and_lf_sha256, write_slim_artifacts
from eplus_gym.mega.pilot_arms import random_continuous_params
from eplus_gym.mega.scored_day_runner import params_for_arm, run_scored_continuity_day
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.reward_v2 import score_day_v2
from eplus_gym.mega.tariff_modes import default_tariff_catalog
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw

AUDIT_ROOT = _APP / "docs" / "audits" / "figures" / "vibe22_reference_247"
DEFAULT_DAY = "2026-01-12"
ARMS = (
    ("observed_bas_incumbent", "incumbent"),
    ("continuous_68", "continuous_68"),
    ("continuous_70", "continuous_70"),
    ("shallow_setback", "shallow_setback"),
    ("deep_setback", "deep_setback"),
    ("FIXED_WEATHER_RULE", "FIXED_WEATHER_RULE"),
    ("FIXED_TOU_RULE", "FIXED_TOU_RULE"),
    ("random", "random"),
)
TARIFF_MODE = "flat_illustrative"
ARM_LABELS = {
    "continuous_70": "CONTINUOUS_70_REFERENCE",
}


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def run_arm(
    *,
    site: Path,
    idf: Path,
    epw: Path,
    day: str,
    arm: str,
    child_bytes: bytes,
    seed: int = 247,
) -> dict:
    label = ARM_LABELS.get(arm, arm)
    day_dir = AUDIT_ROOT / label
    if arm == "random":
        params, raw, _decoded = random_continuous_params(day=day, seed=seed)
        from eplus_gym.control_v2 import build_six_schedules_f
        from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant

        schedules = build_six_schedules_f(params)
        oat = list(forecast_from_epw_replay(epw, day).temps_c)
        plant = EnergyPlusContinuityPlant(
            site_root=site, idf=idf, epw=epw, output=day_dir / "live_run", days=[day]
        )
        plant.start_episode()
        payload = plant.simulate_day(schedules, oat_c=oat)
        gate = plant.finish_quality()
        live = {"gate": gate, "payload": payload, "schedules": schedules}
    else:
        live = run_scored_continuity_day(
            site_root=site,
            idf=idf,
            epw=epw,
            day=day,
            arm=arm,
            output=day_dir / "live_run",
            tariff_mode=TARIFF_MODE,
        )
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    gate = dict(live.get("gate") or {})
    rc = 0 if gate.get("completed_successfully") else 1
    scorecard = build_compact_scorecard(
        label=label,
        day=day,
        arm=arm,
        child_name=A04_IDF_NAME,
        child_idf_byte_sha256=byte_sha,
        child_idf_lf_normalized_sha256=lf_sha,
        gate=gate,
        returncode=rc,
        payload=live.get("payload"),
        physics_status="CONTINUOUS_REFERENCE_NOT_OPERATIONAL_BASELINE",
        rl_eligible=False,
    )
    write_slim_artifacts(day_dir, scorecard)
    scorecard["schedules"] = live.get("schedules")
    scorecard["payload"] = live.get("payload")
    payload = live.get("payload") or {}
    spec = default_tariff_catalog()[TARIFF_MODE]
    rates = spec.hourly_prices()
    rate96 = [rates[i // 4] for i in range(96)]
    fac = list(payload.get("facility_kw") or [])
    zones = payload.get("zone_temps_series_f") or {}
    if len(fac) == 96 and zones:
        scored = score_day_v2(
            day=day,
            candidate_facility_kw=fac,
            candidate_zone_temps_f=zones,
            baseline_facility_kw=fac,
            baseline_zone_temps_f=zones,
            rate_kwh=rate96,
            demand_rate=spec.demand_rate_per_kw,
        )
        scorecard["illustrative_cost_usd"] = scored.candidate["daily_cost"]
    return scorecard


def build_publication_figure(*, day: str, arm_results: list[dict], oat_c: list[float], out: Path) -> Path:
    fig, axes = plt.subplots(6, 1, figsize=(12, 16), sharex=True)
    hours = np.arange(96) * 0.25
    wm = "CONTINUOUS REFERENCE — NOT OPERATIONAL BASELINE"
    for ax in axes:
        ax.text(0.5, 0.5, wm, transform=ax.transAxes, ha="center", va="center", fontsize=14, color="#999", alpha=0.25, rotation=15)

    axes[0].plot(np.arange(24), oat_c, color="#2980b9", linewidth=2)
    axes[0].set_ylabel("OAT °C")
    axes[0].set_title(f"Reference 24/7 conditioning — {day}")

    for sc in arm_results:
        payload = sc.get("payload") or {}
        fac = payload.get("facility_kw") or []
        if len(fac) == 96:
            axes[1].plot(hours, fac, label=sc.get("label"), alpha=0.85)
    axes[1].set_ylabel("Facility kW")
    axes[1].legend(fontsize=7, ncol=2)

    for sc in arm_results:
        payload = sc.get("payload") or {}
        fac = payload.get("facility_kw") or []
        if len(fac) == 96:
            axes[2].plot(hours, np.cumsum(fac) * 0.25, label=sc.get("label"), alpha=0.85)
    axes[2].set_ylabel("Cumulative kWh")

    ref = next((s for s in arm_results if s.get("label") == "CONTINUOUS_70_REFERENCE"), arm_results[0])
    zones = (ref.get("payload") or {}).get("zone_temps_series_f") or {}
    for key in ACTION_KEYS[:6]:
        vals = zones.get(key) or []
        if len(vals) == 96:
            axes[3].plot(hours, vals, label=key, alpha=0.8)
    axes[3].set_ylabel("Zone °F")

    inc = next((s for s in arm_results if s.get("arm") == "incumbent"), ref)
    for sc in arm_results:
        schedules = sc.get("schedules") or {}
        if schedules:
            mean_sp = np.mean([schedules[k] for k in ACTION_KEYS if k in schedules], axis=0)
            if len(mean_sp) == 96:
                axes[4].plot(hours, mean_sp, label=sc.get("label"), alpha=0.75)
    axes[4].set_ylabel("Mean setpoint °F")
    axes[4].legend(fontsize=6, ncol=2)

    ann_lines = []
    for sc in arm_results:
        w2a = sc.get("scored_runtime_w2a_count")
        cost = sc.get("illustrative_cost_usd")
        ready = ((sc.get("readiness") or {}).get("readiness_ok"))
        line = (
            f"{sc.get('label')}: peak={sc.get('peak_kw')} kW, kWh={sc.get('daily_kwh')}, "
            f"W2A={w2a}, ready={ready}"
        )
        if cost is not None:
            line += f", cost=${cost:.0f}"
        ann_lines.append(line)
    axes[5].axis("off")
    axes[5].text(0.01, 0.95, "\n".join(ann_lines), va="top", fontsize=7, family="monospace")
    axes[5].set_xlabel("Cost / W2A / readiness summary")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Vibe22 24/7 reference experiment (publication figure)")
    p.add_argument("--site-root", default="")
    p.add_argument("--day", default=DEFAULT_DAY)
    args = p.parse_args()

    site = require_site_root(args.site_root or None)
    idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned
    day = str(args.day)[:10]
    child_bytes = idf.read_bytes()
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    oat = list(forecast_from_epw_replay(epw, day).temps_c)

    results = []
    for _name, arm in ARMS:
        results.append(
            run_arm(site=site, idf=idf, epw=epw, day=day, arm=arm, child_bytes=child_bytes, seed=247)
        )

    slim_results = []
    for sc in results:
        slim = dict(sc)
        slim.pop("payload", None)
        slim.pop("schedules", None)
        slim_results.append(slim)

    png = build_publication_figure(day=day, arm_results=results, oat_c=oat, out=AUDIT_ROOT / "reference_247_publication.png")
    _write(
        AUDIT_ROOT / "campaign_summary.json",
        {
            "schema": "vibe22.reference_247.v1",
            "day": day,
            "model": A04_IDF_NAME,
            "child_idf_byte_sha256": byte_sha,
            "child_idf_lf_normalized_sha256": lf_sha,
            "honesty_labels": [
                "CONTINUOUS_REFERENCE_NOT_OPERATIONAL_BASELINE",
                "CONTINUOUS_70_REFERENCE",
                "NO_PRISTINE_LOCKED_TEST_AVAILABLE",
            ],
            "arms": slim_results,
            "publication_png": str(png.relative_to(_APP)).replace("\\", "/"),
        },
    )
    print(json.dumps({"day": day, "arms": len(results), "png": str(png)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
