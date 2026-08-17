"""Stage A04 copy for one RunPeriod. Never overwrite the champion."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from eplus_native.idf_stage import (
    disable_sizing_periods,
    ensure_zone_mean_air_temperature_outputs,
    patch_run_period,
)
from eplus_native.six_zone_htg_stage import (
    stage_six_zone_heating_actuators,
    verify_six_zone_staging,
)


def stage_idf_for_period(
    src: Path,
    dest: Path,
    begin: str,
    end: str,
    *,
    site_root: Path | None = None,
    site_config: dict[str, Any] | None = None,
    six_zone_actuators: bool = False,
    disable_sizing: bool = True,
) -> Path:
    src = Path(src)
    dest = Path(dest)
    if dest.resolve() == src.resolve():
        raise ValueError("refusing to overwrite source IDF; pass a staged dest path")
    b = date.fromisoformat(str(begin)[:10])
    e = date.fromisoformat(str(end)[:10])
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = patch_run_period(
        src.read_text(encoding="utf-8"),
        begin_month=b.month,
        begin_day=b.day,
        end_month=e.month,
        end_day=e.day,
        begin_year=b.year,
        end_year=e.year,
        name=f"DSM_{b.isoformat()}_{e.isoformat()}",
    )
    if disable_sizing:
        text = disable_sizing_periods(text)
    text = ensure_zone_mean_air_temperature_outputs(text)
    if six_zone_actuators:
        text, _prov = stage_six_zone_heating_actuators(text)
        verdict = verify_six_zone_staging(text)
        if not verdict["ok"]:
            raise ValueError("six-zone staging failed: " + "; ".join(verdict["issues"]))
    dest.write_text(text, encoding="utf-8")
    return dest
