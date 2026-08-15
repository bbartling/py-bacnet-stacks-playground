"""Field midnight tick — load pickled policy, emit proposal JSON.

Pretend BACnet sibling container: **no WriteProperty**. Writes advisory JSON
to a shared volume for a future human/desktop apply path.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

from eplus_gym.rl import SCREENING_CLAIM, SCHOOL_START_STEP
from eplus_gym.rl.midnight_forecast import load_midnight_forecast
from eplus_gym.rl.policy_pack import DailyPolicyPack
from eplus_gym.rl.spaces import build_day_observation


def midnight_tick(
    *,
    pack_path: Path,
    day: str,
    epw: Path | None = None,
    forecast_source: str = "epw_replay",
    out_path: Path,
    site_occ_f: float = 70.0,
    site_unocc_f: float = 65.0,
    prior_peak_kw: float = 0.0,
    prior_kwh: float = 0.0,
    hourly_override: list[float] | None = None,
) -> Dict[str, Any]:
    pack = DailyPolicyPack.load(Path(pack_path))
    fc = load_midnight_forecast(
        day=day,
        epw=epw,
        source=forecast_source,
        hourly_override=hourly_override,
    )
    d = date.fromisoformat(str(day)[:10])
    mean_c, min_c, max_c, morn_c, h0, hm10 = fc.features()
    obs = build_day_observation(
        month=d.month,
        dow=d.weekday(),
        doy=int(d.strftime("%j")),
        oat_mean_c=mean_c,
        oat_min_c=min_c,
        oat_max_c=max_c,
        prior_peak_kw=prior_peak_kw,
        prior_kwh=prior_kwh,
        site_occ_f=site_occ_f,
        site_unocc_f=site_unocc_f,
        morning_min_c=morn_c,
        hours_below_0c=h0,
        hours_below_m10c=hm10,
        forecast_is_live=0.0 if "replay" in fc.source else 1.0,
    )
    params = pack.predict_params(obs)
    proposal = {
        "scientific_claim": SCREENING_CLAIM,
        "bacnet_writes": False,
        "advisory_only": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "day": fc.day,
        "forecast": fc.to_dict(),
        "school_start_step": SCHOOL_START_STEP,
        "algo": pack.algo,
        "params": params.to_dict(),
        "note": "Advisory only. Heating-setpoint schedule, not occupancy control. "
        "Default hourly [-5C]*24 is a TEST FIXTURE, not OpenWeatherMap. Never auto-write BACnet.",
        "observation_contract": "vibe22.obs.v1_16d_no_zone_temps",
        "forecast_is_test_fixture": True,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    return proposal
