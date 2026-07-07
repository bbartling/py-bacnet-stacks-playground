
# Open-FDD Pandas rule scaffolds for points not present in the Building 100 CSV export.
# These are ready to wire once VAV airflow, damper command, and reheat valve command histories are exported.
import numpy as np
import pandas as pd

def norm_cmd(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return pd.Series(np.where(s > 1.0, s / 100.0, s), index=s.index)

def confirm_fault(raw: pd.Series, poll_seconds: int, confirm_seconds: int = 300) -> pd.Series:
    rows = max(1, int(np.ceil(confirm_seconds / max(poll_seconds, 1))))
    raw = raw.fillna(False).astype(bool)
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw & (streak >= rows)

def vav_command_hunting(df: pd.DataFrame, command_col: str, timestamp_col: str = "timestamp", deadband_pct: float = 3.0, min_reversals_per_hour: int = 6, min_peak_to_peak_pct: float = 10.0) -> pd.Series:
    """Detect VAV damper or reheat valve hunting from command oscillation.
    Use on columns like damper_cmd_pct or reheat_valve_pct.
    Similar intent to Open-FDD FC4 / GL36 operating-state oscillation, but applied to an individual VAV command trace.
    """
    d = df.sort_values(timestamp_col).copy()
    x = pd.to_numeric(d[command_col], errors="coerce")
    dx = x.diff()
    direction = pd.Series(np.where(dx > deadband_pct, 1, np.where(dx < -deadband_pct, -1, 0)), index=d.index)
    nonzero = direction.replace(0, np.nan).ffill().fillna(0)
    reversal = (nonzero != nonzero.shift()) & (nonzero != 0) & (nonzero.shift().fillna(0) != 0)
    poll_seconds = int(d[timestamp_col].diff().dt.total_seconds().median())
    window = max(4, int(round(3600 / poll_seconds)))
    rev_count = reversal.rolling(window, min_periods=window).sum()
    p2p = x.rolling(window, min_periods=window).max() - x.rolling(window, min_periods=window).min()
    raw = (rev_count >= min_reversals_per_hour) & (p2p >= min_peak_to_peak_pct)
    return confirm_fault(raw, poll_seconds, confirm_seconds=3600)

def vav_airflow_sensor_broken(df: pd.DataFrame, airflow_col: str = "airflow_cfm", damper_col: str = "damper_cmd_pct", fan_on_col: str = "ahu_fan_on") -> pd.Series:
    """Flags airflow sensor likely broken: missing/negative, flatlined, or zero airflow while fan/damper indicate flow should exist."""
    airflow = pd.to_numeric(df[airflow_col], errors="coerce")
    damper = norm_cmd(df[damper_col])
    fan_on = df[fan_on_col].fillna(False).astype(bool)
    flat = (airflow.rolling(4, min_periods=4).max() - airflow.rolling(4, min_periods=4).min()) <= 1.0
    raw = airflow.isna() | (airflow < 0) | (fan_on & (damper > 0.30) & (airflow < 5)) | flat
    return confirm_fault(raw, poll_seconds=900, confirm_seconds=300)

def vav_leaking_reheat_valve(df: pd.DataFrame, reheat_valve_col: str = "reheat_valve_pct", discharge_air_temp_col: str = "vav_dat_f", ahu_sat_col: str = "ahu_sat_f") -> pd.Series:
    """Flags likely leaking reheat: valve commanded closed but VAV DAT remains much warmer than AHU SAT."""
    valve = norm_cmd(df[reheat_valve_col])
    dat = pd.to_numeric(df[discharge_air_temp_col], errors="coerce")
    sat = pd.to_numeric(df[ahu_sat_col], errors="coerce")
    raw = (valve < 0.05) & dat.notna() & sat.notna() & ((dat - sat) > 8.0)
    return confirm_fault(raw, poll_seconds=900, confirm_seconds=900)

def bas_vs_open_meteo_weather_fault(df: pd.DataFrame, bas_oat_col: str = "bas_oat_f", web_oat_col: str = "open_meteo_oat_f") -> pd.DataFrame:
    """Warning at ±3°F and fault at ±5°F between local BAS OAT and Open-Meteo weather."""
    out = df.copy()
    out["weather_delta_f"] = pd.to_numeric(out[bas_oat_col], errors="coerce") - pd.to_numeric(out[web_oat_col], errors="coerce")
    out["weather_warning_3f"] = confirm_fault(out["weather_delta_f"].abs() > 3.0, poll_seconds=900, confirm_seconds=300)
    out["weather_fault_5f"] = confirm_fault(out["weather_delta_f"].abs() > 5.0, poll_seconds=900, confirm_seconds=300)
    return out
