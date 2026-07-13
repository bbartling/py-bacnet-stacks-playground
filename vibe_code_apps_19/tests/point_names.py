"""Canonical Haystack point names for synthetic test frames."""
from __future__ import annotations

# Underscore kwargs in tests → Haystack column names on the DataFrame.
TEST_POINT_KWARGS: dict[str, str] = {
    "sat": "discharge-air-temp",
    "sat_sp": "discharge-air-temp-sp",
    "mat": "mixed-air-temp",
    "rat": "return-air-temp",
    "oa_t": "outside-air-temp",
    "oa_h": "outside-air-humidity",
    "oa_damper_pct": "outside-air-damper",
    "clg_valve_pct": "cooling-valve",
    "htg_valve_pct": "heating-valve",
    "fan_cmd": "fan-cmd",
    "return_fan_cmd": "return-fan-cmd",
    "fan_status": "fan-status",
    "duct_static": "duct-static-pressure",
    "duct_static_sp": "duct-static-pressure-sp",
    "zone_t": "zone-air-temp",
    "zone_flow": "zone-airflow",
    "min_flow_sp": "min-flow-sp",
    "damper_pct": "damper",
    "reheat_valve_pct": "reheat-valve",
    "vav_disch_t": "vav-discharge-air-temp",
    "vav_inlet_t": "vav-inlet-air-temp",
    "ahu_sat": "ahu-discharge-air-temp",
    "chw_supply_t": "chilled-water-supply-temp",
    "chw_return_t": "chilled-water-return-temp",
    "hw_supply_t": "hot-water-supply-temp",
    "hw_return_t": "hot-water-return-temp",
    "occ_mode": "occupied",
    "wx_oa_t": "web-outside-air-temp",
    "wx_oa_rh": "web-outside-air-humidity",
    "wx_oa_dewpoint": "web-outside-air-dewpoint",
    "wx_oa_wetbulb": "web-outside-air-wetbulb",
    "chw_pump_cmd": "chw-pump-cmd",
    "chw_pump_status": "chw-pump-status",
    "cw_pump_cmd": "cw-pump-cmd",
    "tower_fan_cmd": "tower-fan-cmd",
    "cw_fan_cmd": "cw-fan-cmd",
    "hw_pump_cmd": "hw-pump-cmd",
    "pump_status": "pump-status",
    "chiller_status": "chiller-status",
    "chiller_amps": "chiller-amps",
    "chiller_power_kw": "chiller-power",
    "elec_power_kw": "elec-power",
    "bas_oa_t": "bas-outside-air-temp",
    "cw_supply_t": "condenser-water-supply-temp",
    "preheat_leave_t": "preheat-leaving-temp",
    "vav_total_flow": "vav-total-airflow",
    "vav_press_req_sum": "vav-pressure-request-sum",
}


def canon_point_cols(cols: dict) -> dict:
    """Map short test kwargs to Haystack DataFrame column names."""
    out = {}
    for k, v in cols.items():
        out[TEST_POINT_KWARGS.get(k, k)] = v
    return out
