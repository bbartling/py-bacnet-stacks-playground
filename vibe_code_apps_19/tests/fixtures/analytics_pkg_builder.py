"""Deterministic multi-equip package for analytics golden baselines.

On-disk copy lives at ``tests/fixtures/analytics_pkg/``. Regenerating files:
``python -c "from tests.fixtures.analytics_pkg_builder import write_analytics_pkg; write_analytics_pkg()"``
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.package_io import SCHEMA_VERSION, SESSION_SCHEMA

FIXTURE_ROOT = Path(__file__).resolve().parent / "analytics_pkg"

# Fixed grid: 90 days @ 6h → enough for weekly motors + multi-month metering, CI-friendly.
_START = "2024-06-01T00:00:00Z"
_PERIODS = 360  # 90 days × 4
_FREQ = "6h"


def _idx() -> pd.DatetimeIndex:
    return pd.date_range(_START, periods=_PERIODS, freq=_FREQ, tz="UTC")


def _ts_col(idx: pd.DatetimeIndex) -> list[str]:
    return idx.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()


def _write_equip(
    root: Path,
    eq_id: str,
    *,
    equip_type: str,
    haystack_points: dict[str, str],
    frame: pd.DataFrame,
) -> None:
    d = root / eq_id
    d.mkdir(parents=True, exist_ok=True)
    frame.to_csv(d / "history_wide.csv", index=False)
    (d / "column_map.json").write_text(
        json.dumps({"equipType": equip_type, "points": haystack_points}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_analytics_pkg(root: Path | None = None) -> Path:
    """Write the deterministic analytics fixture package; return root path."""
    root = Path(root) if root is not None else FIXTURE_ROOT
    if root.exists():
        # Wipe equipment dirs / known files only
        for p in root.rglob("*"):
            if p.is_file():
                p.unlink()
    root.mkdir(parents=True, exist_ok=True)

    idx = _idx()
    ts = _ts_col(idx)
    n = len(idx)
    # Deterministic outdoor pattern (°F)
    oat = [55.0 + 15.0 * ((i % 24) / 24.0) + (i % 7) for i in range(n)]

    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "building_id": "ANALYTICS_GOLDEN_B1",
                "grid_minutes": 360,
                "timezone": "UTC",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    role_map = {
        "AHU_1": {
            "sat": "discharge_air_temp_f",
            "mat": "mixed_air_temp_f",
            "rat": "return_air_temp_f",
            "oa_t": "outside_air_temp_f",
            "fan_status": "supply_fan_status",
            "fan_cmd": "fan_speed_pct",
            "oa_damper_pct": "oa_damper_cmd",
            "duct_static": "duct_static_inwc",
            "clg_valve_pct": "cooling_valve",
        },
        "VAV_1": {
            "zone_t": "zone_temp_f",
            "zone_flow": "zone_airflow_cfm",
            "fan_status": "box_fan_status",
        },
        "CHILLER_1": {
            "chw_supply_t": "chw_supply_temp_f",
            "cw_supply_t": "cw_supply_temp_f",
            "chiller_status": "chiller_run_status",
            "chw_pump_status": "chw_pump_status",
        },
        "BOILER_1": {
            "hw_supply_t": "hw_supply_temp_f",
            "hw_pump_status": "hw_pump_status",
            "boiler_status": "boiler_run_status",
        },
        "COOLING_TOWER_1": {
            "cw_supply_t": "tower_leaving_temp_f",
            "cw_pump_status": "tower_pump_status",
        },
        "METER_1": {
            "elec_power_kw": "building_kw",
            "gas_flow": "gas_therms_per_hr",
        },
    }

    (root / "session_config.json").write_text(
        json.dumps(
            {
                "schema_version": SESSION_SCHEMA,
                "unit_system": "imperial",
                "prefer_web_oat": True,
                "role_map": role_map,
                "params": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    column_map = {
        "version": 1,
        "building": "ANALYTICS_GOLDEN_B1",
        "equipment": {
            eq: {"equipment_type": eq.split("_")[0] if eq != "COOLING_TOWER_1" else "COOLING_TOWER", "column_roles": roles}
            for eq, roles in role_map.items()
        },
    }
    # Fix equipment types in column_map
    column_map["equipment"]["AHU_1"]["equipment_type"] = "AHU"
    column_map["equipment"]["VAV_1"]["equipment_type"] = "VAV"
    column_map["equipment"]["CHILLER_1"]["equipment_type"] = "CHILLER"
    column_map["equipment"]["BOILER_1"]["equipment_type"] = "BOILER"
    column_map["equipment"]["COOLING_TOWER_1"]["equipment_type"] = "COOLING_TOWER"
    column_map["equipment"]["METER_1"]["equipment_type"] = "METER"
    (root / "column_map.json").write_text(json.dumps(column_map, indent=2) + "\n", encoding="utf-8")

    fan_on = [1 if (i % 8) < 6 else 0 for i in range(n)]
    _write_equip(
        root,
        "AHU_1",
        equip_type="ahu",
        haystack_points={
            "discharge-air-temp": "discharge_air_temp_f",
            "mixed-air-temp": "mixed_air_temp_f",
            "return-air-temp": "return_air_temp_f",
            "outside-air-temp": "outside_air_temp_f",
            "fan-status": "supply_fan_status",
            "fan-cmd": "fan_speed_pct",
            "oa-damper": "oa_damper_cmd",
            "duct-static": "duct_static_inwc",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "discharge_air_temp_f": [55.0 + (i % 5) * 0.5 for i in range(n)],
                "mixed_air_temp_f": [62.0 + (i % 3) for i in range(n)],
                "return_air_temp_f": [72.0 + (i % 4) * 0.25 for i in range(n)],
                "outside_air_temp_f": oat,
                "supply_fan_status": fan_on,
                "fan_speed_pct": [40.0 + (i % 10) if fan_on[i] else 0.0 for i in range(n)],
                "oa_damper_cmd": [15.0 + (i % 20) for i in range(n)],
                "duct_static_inwc": [1.2 if fan_on[i] else 0.05 for i in range(n)],
                "cooling_valve": [10.0 if oat[i] > 65 else 0.0 for i in range(n)],
            }
        ),
    )

    zone = [72.0 + ((i % 48) - 24) * 0.15 for i in range(n)]  # some comfort fails
    _write_equip(
        root,
        "VAV_1",
        equip_type="vav",
        haystack_points={
            "zone-air-temp": "zone_temp_f",
            "zone-airflow": "zone_airflow_cfm",
            "fan-status": "box_fan_status",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "zone_temp_f": zone,
                "zone_airflow_cfm": [350.0 if fan_on[i] else 20.0 for i in range(n)],
                "box_fan_status": fan_on,
            }
        ),
    )

    chill_on = [1 if oat[i] > 60 else 0 for i in range(n)]
    _write_equip(
        root,
        "CHILLER_1",
        equip_type="chiller",
        haystack_points={
            "chw-supply-temp": "chw_supply_temp_f",
            "cw-supply-temp": "cw_supply_temp_f",
            "chiller-status": "chiller_run_status",
            "pump-status": "chw_pump_status",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "chw_supply_temp_f": [44.0 + (oat[i] - 70) * 0.05 for i in range(n)],
                "cw_supply_temp_f": [78.0 + (oat[i] - 70) * 0.2 for i in range(n)],
                "chiller_run_status": chill_on,
                "chw_pump_status": chill_on,
            }
        ),
    )

    boil_on = [1 if oat[i] < 58 else 0 for i in range(n)]
    _write_equip(
        root,
        "BOILER_1",
        equip_type="boiler",
        haystack_points={
            "hw-supply-temp": "hw_supply_temp_f",
            "boiler-status": "boiler_run_status",
            "pump-status": "hw_pump_status",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "hw_supply_temp_f": [160.0 - (oat[i] - 50) * 0.8 for i in range(n)],
                "boiler_run_status": boil_on,
                "hw_pump_status": boil_on,
            }
        ),
    )

    _write_equip(
        root,
        "COOLING_TOWER_1",
        equip_type="coolingTower",
        haystack_points={
            "cw-supply-temp": "tower_leaving_temp_f",
            "pump-status": "tower_pump_status",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "tower_leaving_temp_f": [75.0 + (oat[i] - 70) * 0.3 for i in range(n)],
                "tower_pump_status": chill_on,
            }
        ),
    )

    _write_equip(
        root,
        "METER_1",
        equip_type="meter",
        haystack_points={
            "elec-power": "building_kw",
            "gas-flow": "gas_therms_per_hr",
        },
        frame=pd.DataFrame(
            {
                "timestamp_utc": ts,
                "building_kw": [80.0 + oat[i] * 0.8 + (i % 5) for i in range(n)],
                "gas_therms_per_hr": [max(0.0, 2.0 - oat[i] * 0.02) for i in range(n)],
            }
        ),
    )

    wx = root / "weather"
    wx.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp_utc": ts,
            "wx_oa_t": oat,
            "wx_oa_rh": [45.0 + (i % 20) for i in range(n)],
        }
    ).to_csv(wx / "history_wide.csv", index=False)

    return root


if __name__ == "__main__":
    p = write_analytics_pkg()
    print(f"Wrote analytics fixture package → {p}")
