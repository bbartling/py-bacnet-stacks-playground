"""Fan runtime analytics."""

from __future__ import annotations

import pandas as pd

from app.rules.base import finalize, norm_cmd


def fan_runtime_hours(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    thr = float(params.get("fan_on_frac", 0.05))
    fan = norm_cmd(df.get("fan_cmd")).fillna(0)
    raw = fan > thr
    r = finalize("FAN-RUNTIME", df.attrs.get("equipment_id", ""), raw, poll_seconds, 0)
    r.message = f"runtime={r.fault_hours:.1f}h"
    r.plot_series = {"fan_cmd": fan}
    return r
