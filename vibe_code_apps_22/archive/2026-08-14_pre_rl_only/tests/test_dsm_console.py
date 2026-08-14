"""DSM console helpers (lookup / live routing + KPIs)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import time

from eplus_gym.controllers import RuleController
from eplus_gym.lookup_emulator import STEPS
from eplus_gym.simulate import day_for_step
from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym_app.dsm_console import (
    attach_baseline_deltas,
    coalesce_frame,
    daily_peaks_from_traj,
    default_calendar_month,
    dsm_kpis,
    frame_map,
    live_run_jobs,
    meter_peak_day_for_period,
    period_run_spec,
    pick_frame,
    resolve_dsm_mode,
    run_dsm_lookup,
    stage_idf_for_day,
    stage_idf_for_period,
    strategy_library,
)
from eplus_gym_app.weather_files import (
    KIND_AMY,
    KIND_TMY_MSN,
    KIND_TMY_SCREENING,
    classify_epw,
    epws_for_mode,
    resolve_amy_epw,
    resolve_tmy_msn_epw,
    weather_inventory,
)


def _w2a_farm(site: Path, day: str = "2026-01-26") -> None:
    farm = site / "eplus" / "dsm_farm_w2a"
    farm.mkdir(parents=True)
    rows = []
    for sid, base in (("baseline", 200.0), ("deep_setback", 160.0)):
        for q in range(STEPS):
            rows.append(
                {
                    "day": day,
                    "strategy_id": sid,
                    "quarter_index": q,
                    "facility_kw": base + 0.2 * q,
                    "oat_f": 8.0,
                }
            )
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_w2a_15min_v1.parquet", index=False)


def test_resolve_lookup_when_w2a_farm_exists(tmp_path: Path):
    _w2a_farm(tmp_path)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "lookup"
    assert "farm" in reason.lower()


def test_resolve_error_without_farm_or_live(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("eplus_gym_app.dsm_console.energyplus_available", lambda: False)
    mode, reason = resolve_dsm_mode(tmp_path)
    assert mode == "error"
    assert "IdealLoads" in reason


def test_dsm_kpis_vs_baseline_and_actual():
    df = pd.DataFrame({"facility_kw": [100.0, 200.0, 150.0]})
    kpis = dsm_kpis(
        df,
        {"honesty": "W2A_PHYSICAL_DSM", "provenance": "FARM_LOOKUP_EMULATOR", "promote": False},
        actual_peak_kw=220.0,
        baseline_peak_kw=250.0,
        baseline_kwh=200.0,
    )
    assert kpis["peak_kw"] == pytest.approx(200.0)
    assert kpis["kwh"] == pytest.approx((100 + 200 + 150) * 0.25)
    assert kpis["kw_trim"] == pytest.approx(50.0)
    assert kpis["kwh_penalty"] == pytest.approx((100 + 200 + 150) * 0.25 - 200.0)
    assert kpis["vs_actual_pct"] == pytest.approx((200 - 220) / 220 * 100)
    assert kpis["vs_baseline_pct"] == pytest.approx((200 - 250) / 250 * 100)
    assert kpis["promote"] is False


def test_attach_baseline_deltas_window_totals():
    kpis = {
        "baseline": {"peak_kw": 200.0, "kwh": 1000.0},
        "deep_setback": {"peak_kw": 160.0, "kwh": 1100.0},
    }
    attach_baseline_deltas(kpis)
    assert kpis["baseline"]["kw_trim"] == pytest.approx(0.0)
    assert kpis["baseline"]["kwh_penalty"] == pytest.approx(0.0)
    assert kpis["deep_setback"]["kw_trim"] == pytest.approx(40.0)
    assert kpis["deep_setback"]["kwh_penalty"] == pytest.approx(100.0)


def test_run_dsm_lookup_returns_frame(tmp_path: Path):
    _w2a_farm(tmp_path)
    pack = run_dsm_lookup(
        site_root=tmp_path,
        strategy_id="deep_setback",
        day="2026-01-26",
    )
    assert pack["meta"]["family"] == "w2a"
    assert pack["meta"]["honesty"] == "W2A_PHYSICAL_DSM"
    assert pack["meta"]["loop"] == "CLOSED_LOOP_RULE_DR"
    assert pack["meta"]["promote"] is False
    assert not pack["frame"].empty
    assert pack["kpis"]["peak_kw"] < 220
    assert "day" in pack["frame"].columns
    assert pack["frame"]["day"].iloc[0] == "2026-01-26"


def test_stage_idf_for_period_writes_window_without_touching_source(tmp_path: Path):
    src = tmp_path / "champion.idf"
    src.write_text(
        "RunPeriod,\n"
        "  CalibrationWindow,  !- Name\n"
        "  8,                  !- Begin Month\n"
        "  1,                  !- Begin Day of Month\n"
        "  2025,               !- Begin Year\n"
        "  7,                  !- End Month\n"
        "  2,                  !- End Day of Month\n"
        "  2026;               !- End Year\n",
        encoding="utf-8",
    )
    dest = tmp_path / "staged.idf"
    stage_idf_for_period(src, dest, "2025-12-01", "2026-02-28")
    assert "CalibrationWindow" in src.read_text(encoding="utf-8")
    staged = dest.read_text(encoding="utf-8")
    assert "DSM_2025-12-01_2026-02-28" in staged
    assert "12," in staged
    assert "28," in staged
    with pytest.raises(ValueError, match="overwrite"):
        stage_idf_for_period(src, src, "2025-12-01", "2026-02-28")


def test_pick_frame_avoids_dataframe_truthiness():
    amy = pd.DataFrame({"facility_kw": [1.0, 2.0]})
    tmy = pd.DataFrame({"facility_kw": [3.0]})
    frames = {
        f"baseline:{KIND_AMY}": amy,
        f"baseline:{KIND_TMY_MSN}": tmy,
    }
    got = pick_frame(frames, f"baseline:{KIND_AMY}", f"baseline:{KIND_TMY_MSN}")
    assert got is amy
    only_tmy = pick_frame(
        {f"baseline:{KIND_TMY_MSN}": tmy},
        f"baseline:{KIND_AMY}",
        f"baseline:{KIND_TMY_MSN}",
    )
    assert only_tmy is tmy
    assert pick_frame({}, f"baseline:{KIND_AMY}") is None


def test_frame_map_and_coalesce_ignore_dataframe_truthiness():
    amy = pd.DataFrame({"facility_kw": [1.0, 2.0]})
    assert frame_map(amy) == {}
    assert frame_map({"baseline:amy": amy, "skip": 1}) == {"baseline:amy": amy}
    assert coalesce_frame(None, amy, pd.DataFrame({"facility_kw": [9.0]})) is amy
    assert coalesce_frame(None, "x", None) is None
    # Regression: these used to raise ValueError on bool(DataFrame)
    assert frame_map({"k": amy}).get("k") is amy


def test_period_run_spec_day_month_year_step_counts():
    day_ctx = {"day": "2026-01-26", "window_days": ["2026-01-26"]}
    day = period_run_spec(day_ctx, "Peak day")
    assert day["n_days"] == 1
    assert day["max_steps"] == 96
    assert day["period"] == "2026-01-26/2026-01-26"

    month_days = [f"2026-01-{d:02d}" for d in range(1, 32)]
    month = period_run_spec(
        {"day": "2026-01-26", "window_days": month_days}, "Calendar month"
    )
    assert month["begin"] == "2026-01-01"
    assert month["end"] == "2026-01-31"
    assert month["n_days"] == 31
    assert month["max_steps"] == 31 * 96

    year = period_run_spec(
        {
            "day": "2026-01-26",
            "window_days": ["2026-01-01", "2026-06-15", "2026-12-31"],
        },
        "Calendar year",
    )
    assert year["begin"] == "2026-01-01"
    assert year["end"] == "2026-12-31"
    assert year["n_days"] == 365
    assert year["max_steps"] == 365 * 96


def test_period_run_spec_three_day_window_is_288_steps():
    ctx = {
        "day": "2026-01-26",
        "window_days": ["2026-01-25", "2026-01-26", "2026-01-27"],
    }
    spec = period_run_spec(ctx, "Peak week")
    assert spec["max_steps"] == 288
    assert spec["n_days"] == 3
    assert spec["begin"] == "2026-01-25"
    assert spec["end"] == "2026-01-27"
    peak = period_run_spec(ctx, "Peak day")
    assert peak["max_steps"] == 96
    ctrl = RuleController("baseline")
    assert ctrl.setpoint_f(0) == ctrl.setpoint_f(96)
    assert ctrl.setpoint_f(5) == ctrl.setpoint_f(101)
    assert day_for_step("2026-01-25", 0) == "2026-01-25"
    assert day_for_step("2026-01-25", 96) == "2026-01-26"
    assert day_for_step("2026-01-25", 287) == "2026-01-27"


def test_period_run_spec_winter_is_full_calendar_span():
    ctx = {
        "day": "2026-01-26",
        "window_days": ["2025-12-01", "2026-01-15", "2026-02-28"],
    }
    spec = period_run_spec(ctx, "Winter (Dec-Feb)")
    assert spec["begin"] == "2025-12-01"
    assert spec["end"] == "2026-02-28"
    assert spec["n_days"] == 90
    assert spec["max_steps"] == 90 * 96
    assert spec["period"] == "2025-12-01/2026-02-28"


def test_weather_resolver_amy_found_chicago_not_auto_tmy(tmp_path: Path):
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    amy = weather / "madison_amy_202508_202607.epw"
    screening = weather / "madison_tmy_screening.epw"
    chicago = weather / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
    amy.write_text("EPW", encoding="utf-8")
    screening.write_text("EPW", encoding="utf-8")
    chicago.write_text("EPW", encoding="utf-8")
    assert classify_epw(amy) == KIND_AMY
    assert classify_epw(screening) == KIND_TMY_SCREENING
    assert classify_epw(chicago) == KIND_TMY_SCREENING
    assert resolve_amy_epw(tmp_path) == amy
    assert resolve_tmy_msn_epw(tmp_path) is None
    inv = weather_inventory(tmp_path)
    assert inv["default_mode"] == "AMY"
    assert inv["tmy"] is None
    assert "Chicago" in (inv["tmy_missing_note"] or "")
    both = epws_for_mode("Both", inv)
    assert both == [(KIND_AMY, amy)]
    real = weather / "USA_WI_Madison-Dane.County.AP.726410_TMY3.epw"
    real.write_text("EPW", encoding="utf-8")
    assert classify_epw(real) == KIND_TMY_MSN
    assert resolve_tmy_msn_epw(tmp_path) == real
    inv2 = weather_inventory(tmp_path)
    assert inv2["default_mode"] == "AMY"
    assert epws_for_mode("Both", inv2) == [(KIND_AMY, amy), (KIND_TMY_MSN, real)]


def test_daily_peak_overlay_accepts_two_or_three_series():
    from eplus_gym_app.plots import period_daily_peak_figure

    daily = pd.DataFrame(
        {"local_day": ["2026-01-25", "2026-01-26", "2026-01-27"], "peak_kw": [200.0, 286.0, 180.0]}
    )
    amy = pd.DataFrame(
        {"local_day": ["2026-01-25", "2026-01-26", "2026-01-27"], "peak_kw": [190.0, 198.0, 170.0]}
    )
    tmy = pd.DataFrame(
        {"local_day": ["2026-01-25", "2026-01-26", "2026-01-27"], "peak_kw": [185.0, 192.0, 168.0]}
    )
    fig = period_daily_peak_figure(
        daily,
        highlight_day="2026-01-26",
        title="winter both",
        eplus_daily={"E+ AMY": amy, "E+ TMY": tmy},
    )
    assert len(fig.data) == 3
    names = {t.name for t in fig.data}
    assert "Actual BAS daily peak kW" in names
    assert "E+ AMY" in names
    assert "E+ TMY" in names
    agg = daily_peaks_from_traj(
        pd.DataFrame(
            {
                "step": list(range(192)),
                "day": ["2026-01-25"] * 96 + ["2026-01-26"] * 96,
                "facility_kw": [100.0] * 95 + [140.0] + [110.0] * 95 + [155.0],
            }
        )
    )
    assert list(agg["local_day"]) == ["2026-01-25", "2026-01-26"]
    assert agg["peak_kw"].tolist() == pytest.approx([140.0, 155.0])


def test_stage_idf_for_day_does_not_overwrite_source(tmp_path: Path):
    src = tmp_path / "champion.idf"
    src.write_text(
        "RunPeriod,\n"
        "  CalibrationWindow,  !- Name\n"
        "  8,                  !- Begin Month\n"
        "  1,                  !- Begin Day of Month\n"
        "  2025,               !- Begin Year\n"
        "  7,                  !- End Month\n"
        "  2,                  !- End Day of Month\n"
        "  2026;               !- End Year\n",
        encoding="utf-8",
    )
    dest = tmp_path / "staged.idf"
    stage_idf_for_day(src, dest, "2026-01-26")
    assert "CalibrationWindow" in src.read_text(encoding="utf-8")
    staged = dest.read_text(encoding="utf-8")
    assert "DSM_2026-01-26" in staged
    assert "26," in staged
    with pytest.raises(ValueError, match="overwrite"):
        stage_idf_for_day(src, src, "2026-01-26")


def test_persist_and_load_last_run(tmp_path: Path):
    from eplus_gym_app.dsm_console import persist_last_run

    df = pd.DataFrame({"step": [0, 1], "facility_kw": [100.0, 120.0]})
    actual = pd.DataFrame({"hod": [0.0, 1.0], "kw_avg": [200.0, 210.0]})
    pq = tmp_path / "traj.parquet"
    df.to_parquet(pq, index=False)
    persist_last_run(
        tmp_path,
        df=df,
        actual=actual,
        kpis={"peak_kw": 120.0},
        strategy="baseline",
        day="2026-01-26",
        preset="Winter (Dec-Feb)",
        mode="live",
        epw_name="madison_amy_202508_202607.epw",
        why="test",
        window_days=["2025-12-01", "2026-01-26", "2026-02-28"],
        parquet=str(pq),
        weather_mode="AMY",
        period="2025-12-01/2026-02-28",
        max_steps=8640,
        n_days=90,
        parquets={"AMY_OPEN_METEO": str(pq)},
        weather_kind="AMY_OPEN_METEO",
    )
    ptr = tmp_path / "reports" / "eplus_gym" / "last_dsm_run.json"
    doc = json.loads(ptr.read_text(encoding="utf-8"))
    assert "frame" not in doc
    assert doc["parquet"] == str(pq)
    assert doc["day"] == "2026-01-26"
    assert doc["period"] == "2025-12-01/2026-02-28"
    assert doc["max_steps"] == 8640
    assert doc["loop"] == "CLOSED_LOOP_RULE_DR"
    assert doc["weekend_sp"] == "repeat_96_step_profile"
    assert doc["promote"] is False
    assert doc["weather_kind"] == "AMY_OPEN_METEO"


def test_period_daily_peak_figure_highlights_sim_day():
    from eplus_gym_app.plots import period_daily_peak_figure

    daily = pd.DataFrame(
        {"local_day": ["2026-01-25", "2026-01-26", "2026-01-27"], "peak_kw": [200.0, 286.0, 180.0]}
    )
    fig = period_daily_peak_figure(
        daily, highlight_day="2026-01-26", title="winter", eplus_peak_kw=199.0
    )
    assert len(fig.data) == 1
    assert fig.layout.title.text == "winter"


def test_default_calendar_month_is_peak_day_month_not_earliest():
    months = ["2025-08", "2025-12", "2026-01", "2026-02"]
    assert default_calendar_month(months, "2026-01-26") == "2026-01"
    assert default_calendar_month(months, "2025-12-15") == "2025-12"
    assert default_calendar_month(months, None) == "2025-08"


def test_meter_peak_day_calendar_month_not_always_anchor():
    rows = []
    for day, peak in (("2026-01-26", 280.0), ("2026-02-03", 190.0), ("2026-02-14", 240.0)):
        for h in range(24):
            rows.append(
                {
                    "hour_utc": pd.Timestamp(f"{day}T{h:02d}:00:00+00:00"),
                    "kw_avg": peak if h == 8 else 80.0,
                    "oat_f": 10.0,
                    "local_day": day,
                    "hod": float(h),
                }
            )
    bas = pd.DataFrame(rows)
    jan = meter_peak_day_for_period(
        bas, preset="Peak day", peak_anchor="2026-01-26"
    )
    assert jan["day"] == "2026-01-26"
    feb = meter_peak_day_for_period(
        bas, preset="Calendar month", peak_anchor="2026-01-26", month="2026-02"
    )
    assert feb["day"] == "2026-02-14"
    assert feb["actual_peak_kw"] == pytest.approx(240.0)
    assert "2026-02" in feb["why"]


def test_meter_index_zero_from_api_csv():
    from eplus_gym.runner import _meter_indices_from_api_csv, _meter_lookup_key

    raw = (
        b"**ACTUATORS**\n"
        b"Actuator,Foo,Bar,Baz,[W]\n"
        b"**METERS**\n"
        b"OutputMeter,Electricity:Facility,J\n"
        b"OutputMeter,Electricity:Building,J\n"
        b"**VARIABLES**\n"
        b"OutputVariable,Site Outdoor Air Drybulb Temperature,Environment,C\n"
    )
    idx = _meter_indices_from_api_csv(raw)
    assert idx[_meter_lookup_key("Electricity:Facility")] == 0
    assert idx["ELECTRICITY:BUILDING"] == 1
    assert "SITE OUTDOOR AIR DRYBULB TEMPERATURE" not in idx


def test_format_hms_and_wait_live_subprocess_updates_status():
    from eplus_gym_app.dsm_console import format_hms, wait_live_subprocess

    assert format_hms(0) == "0s"
    assert format_hms(12.4) == "12s"
    assert format_hms(65) == "1m 05s"
    assert format_hms(3661) == "1h 01m 01s"

    class _FakeProc:
        def __init__(self):
            self._n = 0
            self.returncode = None

        def poll(self):
            self._n += 1
            if self._n >= 3:
                self.returncode = 0
                return 0
            return None

    class _FakeStatus:
        def __init__(self):
            self.labels: list[str] = []

        def update(self, *, label: str, state: str):
            self.labels.append(label)
            assert state == "running"

    status = _FakeStatus()
    code, elapsed = wait_live_subprocess(
        _FakeProc(),
        status=status,
        job_label="baseline · AMY",
        campaign_t0=time.perf_counter(),
        job_t0=time.perf_counter(),
        job_index=1,
        job_total=5,
        poll_s=0.01,
    )
    assert code == 0
    assert elapsed >= 0
    assert status.labels
    assert "1/5" in status.labels[-1]
    assert "total" in status.labels[-1]


def test_start_live_subprocess_passes_begin_end_max_steps(tmp_path: Path, monkeypatch):
    from eplus_gym_app.dsm_console import start_live_subprocess

    captured: dict = {}

    class _FakeProc:
        pass

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = [str(x) for x in cmd]
        return _FakeProc()

    monkeypatch.setattr("eplus_gym_app.dsm_console.subprocess.Popen", _fake_popen)
    epw = tmp_path / "madison_amy_202508_202607.epw"
    idf = tmp_path / "champ.idf"
    epw.write_text("EPW", encoding="utf-8")
    idf.write_text("IDF", encoding="utf-8")
    proc, handle, log = start_live_subprocess(
        site=tmp_path,
        strategy_id="baseline",
        epw=epw,
        idf=idf,
        out_dir=tmp_path / "out",
        begin="2025-12-01",
        end="2026-02-28",
        max_steps=8640,
    )
    handle.close()
    assert proc is not None
    assert log.name == "live.log"
    cmd = captured["cmd"]
    assert "--mode" in cmd and "live" in cmd
    assert "--family" in cmd and "w2a" in cmd
    assert cmd[cmd.index("--begin") + 1] == "2025-12-01"
    assert cmd[cmd.index("--end") + 1] == "2026-02-28"
    assert cmd[cmd.index("--max-steps") + 1] == "8640"
    assert cmd[cmd.index("--day") + 1] == "2025-12-01"


def test_summarize_eplus_failure_from_live_log(tmp_path: Path):
    from eplus_gym_app.dsm_console import summarize_eplus_failure

    log = tmp_path / "live.log"
    log.write_text(
        "Program terminated: EnergyPlus Terminated--Error(s) Detected.\n"
        "AttributeError: 'NoneType' object has no attribute 'values'\n"
        "FileNotFoundError: W2A live EnergyPlus failed; will not fall back to IdealLoads\n",
        encoding="utf-8",
    )
    msg = summarize_eplus_failure(log, exit_code=1)
    assert "exit code 1" in msg
    assert "terminated" in msg.lower()
    assert "IdealLoads" in msg or "obs" in msg.lower() or "None" in msg



def test_strategy_library_lists_five_desktop_contracts():
    lib = strategy_library()
    ids = [r["strategy_id"] for r in lib["rows"]]
    assert ids == list(DEPLOYABLE_STRATEGIES)
    assert "index" not in ids
    assert all(not s.startswith("prbs") for s in ids)
    assert all(len(lib["series"][s]) == 96 for s in ids)


def test_live_run_jobs_five_strategies_per_weather(tmp_path: Path):
    amy = tmp_path / "amy.epw"
    tmy = tmp_path / "tmy.epw"
    amy.write_text("EPW", encoding="utf-8")
    tmy.write_text("EPW", encoding="utf-8")
    one = live_run_jobs(
        strategies=list(DEPLOYABLE_STRATEGIES),
        weathers=[("AMY_OPEN_METEO", amy)],
        begin="2026-01-01",
        end="2026-01-03",
        max_steps=288,
    )
    assert len(one) == 5
    assert [j["strategy_id"] for j in one] == list(DEPLOYABLE_STRATEGIES)
    assert all(j["max_steps"] == 288 for j in one)
    both = live_run_jobs(
        strategies=list(DEPLOYABLE_STRATEGIES),
        weathers=[("AMY_OPEN_METEO", amy), ("TMY_MSN", tmy)],
        begin="2026-01-01",
        end="2026-01-03",
        max_steps=288,
    )
    assert len(both) == 10
    assert both[0]["key"] == "baseline:AMY_OPEN_METEO"
