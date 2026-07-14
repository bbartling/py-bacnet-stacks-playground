"""Per-sensor SV evidence, AHU-DUCTHI pressure gate, SCHED-247 pressure, RCx labels."""

from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import sensor_fault_summary, sensor_health_matrix
from app.rcx_plots import PRESETS, zone_comfort_fail_ranking
from app.rules import run_rule
from app.rules.cookbook_catalog import RULES_BY_ID, _sweep_range
from tests.point_names import canon_point_cols


def _ahu_df(n: int = 24, **cols) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    data = {k: ([v] * n if not isinstance(v, list) else v) for k, v in canon_point_cols(cols).items()}
    df = pd.DataFrame(data, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    return df


def test_sweep_range_stashes_per_role_evidence() -> None:
    # SAT way out of range; RAT normal
    df = _ahu_df(sat=200.0, rat=72.0, mat=70.0, oa_t=50.0)
    mask = _sweep_range(df, {"confirm_min": 0}, 300.0)
    assert bool(mask.any())
    ev = df.attrs.get("sv_sweep_evidence") or []
    by_role = {e["role"]: e for e in ev}
    assert by_role["discharge-air-temp"]["faulted"] is True
    assert by_role["return-air-temp"]["faulted"] is False
    assert "sensor_type" in by_role["discharge-air-temp"]


def test_sensor_fault_summary_only_lists_faulted_sensors() -> None:
    df = _ahu_df(sat=200.0, rat=72.0, mat=70.0, oa_t=50.0, fan_cmd=50.0)
    r = run_rule(
        "SV-RANGE",
        df,
        {"confirm_min": 0, "startup_delay_min": 0},
        300.0,
        require_operational_gates=False,
    )
    assert r.status == "FAULT"
    assert r.metrics.get("sv_sweep_evidence")
    summary = sensor_fault_summary(df, [r], equipment_id="AHU_1")
    sensors = set(summary["sensor"].astype(str))
    assert "discharge-air-temp" in sensors
    assert "return-air-temp" not in sensors  # healthy — must not inherit OR window


def test_sensor_health_matrix_has_rule_columns() -> None:
    df = _ahu_df(sat=200.0, rat=72.0, fan_cmd=50.0)
    r = run_rule("SV-RANGE", df, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    mat = sensor_health_matrix(df, [r], equipment_id="AHU_1")
    assert "SV-RANGE" in mat.columns
    row = mat[mat["sensor"] == "discharge-air-temp"].iloc[0]
    assert row["SV-RANGE"] != "OK"


def test_ahu_ducthi_faults_with_fan_status_off_high_static() -> None:
    """Regression: fan_running gate used to hide high static when status is off."""
    n = 24
    df = _ahu_df(
        n,
        duct_static=[2.5] * n,
        duct_static_sp=[1.0] * n,
        fan_status=[0] * n,
        fan_cmd=[0.0] * n,
    )
    r = run_rule(
        "AHU-DUCTHI",
        df,
        {"confirm_min": 0, "duct_high_margin": 0.25, "pressure_on_min": 0.2, "startup_delay_min": 0},
        300.0,
        require_operational_gates=True,
    )
    assert r.status == "FAULT", r.notes
    assert r.metrics.get("gate_source", "").startswith("fan_or_duct_static") or "duct_static" in str(
        r.metrics.get("gate_source", "")
    )


def test_sched247_uses_duct_static_as_on_evidence() -> None:
    n = 40
    # fan status/cmd off, but duct static pressurized entire window
    df = _ahu_df(
        n,
        fan_status=[0] * n,
        fan_cmd=[0.0] * n,
        duct_static=[1.5] * n,
    )
    r = run_rule(
        "SCHED-247",
        df,
        {"confirm_min": 0, "always_on_pct": 0.90, "pressure_on_min": 0.2},
        300.0,
        require_operational_gates=False,
    )
    assert r.status == "FAULT", r.notes


def test_rcx_non_tower_scatter_presets_say_dry_bulb() -> None:
    wet_ok = {"cw_reset_scatter"}
    for p in PRESETS:
        if p.chart != "scatter_oat":
            continue
        title = (p.title or "").lower()
        desc = (p.description or "").lower()
        if p.id in wet_ok:
            assert "wet" in title or "wet" in desc
        else:
            assert "wet" not in title
            assert "dry-bulb" in title or "dry bulb" in title


def test_zone_comfort_ranking_has_below_above_splits() -> None:
    from app.occupancy import OccupancySchedule

    # Midday America/Chicago (schedule default tz) so samples fall in 06:00–18:00 occupied window
    idx = pd.date_range("2024-06-03 14:00", periods=10, freq="h", tz="UTC")  # Monday ≈ 09:00 CDT
    df = pd.DataFrame(
        {"zone-air-temp": [65, 65, 72, 72, 80, 80, 72, 72, 72, 72]},
        index=idx,
    )
    df.attrs["equipment_type"] = "VAV"
    frames = {"VAV_1": df}
    role_map = {"VAV_1": {"zone-air-temp": "zone-air-temp"}}
    rank = zone_comfort_fail_ranking(
        frames,
        role_map,
        schedule=OccupancySchedule(),
        comfort_low_f=70.0,
        comfort_high_f=75.0,
    )
    assert not rank.empty
    assert "n_below" in rank.columns and "n_above" in rank.columns
    assert int(rank.iloc[0]["n_below"]) >= 1
    assert int(rank.iloc[0]["n_above"]) >= 1


def test_oat_meteo_has_oat_err_param() -> None:
    p = next(x for x in RULES_BY_ID["OAT-METEO"].params if x.key == "oat_err")
    assert p.direction == "fewer"
