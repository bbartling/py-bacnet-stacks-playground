"""Build 19-D obs v2 plus unnormalized sidecar (shared by env and eval)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.spaces import build_day_observation


def observation_and_context(
    *,
    day: str,
    epw: Path,
    billing_floor_kw: float,
    zone_temps_f: Sequence[float],
    mtd_peak_kw: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    d = date.fromisoformat(str(day)[:10])
    fc = forecast_from_epw_replay(Path(epw), d)
    mean_c, min_c, max_c, morn_c, h0, hm10 = fc.features()
    floor = float(billing_floor_kw)
    mtd = float(mtd_peak_kw if mtd_peak_kw is not None else floor)
    temps = [float(x) for x in zone_temps_f]
    if len(temps) != 6:
        raise ValueError("need 6 zone temps")
    ctx = {
        "day": d.isoformat(),
        "month": d.month,
        "dow": d.weekday(),
        "doy": int(d.strftime("%j")),
        "oat_mean_c": mean_c,
        "oat_min_c": min_c,
        "oat_max_c": max_c,
        "morning_min_c": morn_c,
        "hours_below_0c": h0,
        "hours_below_m10c": hm10,
        "billing_floor_kw": floor,
        "mtd_peak_kw": mtd,
        "illustrative_school_day": 1.0 if d.weekday() < 5 else 0.0,
        "zone_temps_f": temps,
        "forecast_is_live": 0.0,
        "obs_schema": "vibe22.obs.v2",
    }
    obs = build_day_observation(
        month=ctx["month"],
        dow=ctx["dow"],
        doy=ctx["doy"],
        oat_mean_c=mean_c,
        oat_min_c=min_c,
        oat_max_c=max_c,
        billing_floor_kw=floor,
        mtd_peak_kw=mtd,
        morning_min_c=morn_c,
        hours_below_0c=h0,
        hours_below_m10c=hm10,
        forecast_is_live=0.0,
        illustrative_school_day=ctx["illustrative_school_day"],
        zone_temps_f=temps,
    )
    return obs, ctx
