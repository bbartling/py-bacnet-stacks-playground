"""DSM campaign / preflight / startup error regressions."""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.errors import EnergyPlusStartupError
from eplus_gym.startup_diag import diagnose_startup_failure
from eplus_gym_app.dsm_campaign import (
    build_jobs,
    default_strategy_selection,
    elapsed_seconds,
    mark_failed,
    new_campaign_doc,
    read_json,
    reconcile_campaign,
    validate_job_outputs,
    write_campaign,
)
from eplus_gym_app.dsm_preflight import PreflightError, run_preflight
from eplus_gym_app.open_meteo_epw import parse_epw_span, publish_current_amy, write_epw, to_local_standard
from eplus_gym_app.weather_files import KIND_AMY, weather_inventory


def _tiny_epw(path: Path, *, start: date, days: int) -> Path:
    rows = []
    for d in range(days):
        day = date.fromordinal(start.toordinal() + d)
        for h in range(24):
            rows.append(
                f"{day.year},{day.month},{day.day},{h + 1},0,"
                "20.0,10.0,50,101325,0,0,0,0,0,0,0,0,0,0,3,270,0,0,0,0,0,0,0,0,0,0,0,0,0"
            )
    # Minimal EPW header + data (parse_epw_span skips alpha lines)
    path.write_text(
        "LOCATION,Test,WI,USA,TMY3,726410,43.17,-89.25,-6.0,261.0\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return path


def test_no_js_hud_in_dsm_console():
    src = Path(__file__).resolve().parents[1] / "eplus_gym_app" / "dsm_console.py"
    text = src.read_text(encoding="utf-8")
    assert "setInterval" not in text
    assert "__dsmBumpSim" not in text
    assert "st.html" not in text
    assert "unsafe_allow_javascript" not in text


def test_default_job_list_baseline_plus_one():
    assert default_strategy_selection("deep_setback") == ["baseline", "deep_setback"]
    jobs = build_jobs(
        strategies=default_strategy_selection("deep_setback"),
        weather_mode="AMY",
        amy=Path("amy.epw"),
        tmy=Path("tmy.epw"),
        begin="2026-07-01",
        end="2026-07-01",
        max_steps=96,
    )
    assert len(jobs) == 2
    assert {j["strategy_id"] for j in jobs} == {"baseline", "deep_setback"}


def test_preflight_rejects_end_outside_epw(tmp_path: Path, monkeypatch):
    start = date(2025, 8, 1)
    end = date(2026, 7, 2)
    days = (end - start).days + 1
    epw = _tiny_epw(tmp_path / "amy.epw", start=start, days=days)
    span = parse_epw_span(epw)
    assert span["end"] == end
    idf = tmp_path / "champ.idf"
    idf.write_text("Version,24.2;\n", encoding="utf-8")
    monkeypatch.setattr("eplus_gym_app.dsm_preflight.energyplus_available", lambda: True)
    with pytest.raises(PreflightError) as ei:
        run_preflight(
            idf=idf,
            epws=[epw],
            begin="2026-01-01",
            end="2026-07-03",
            max_steps=((date(2026, 7, 3) - date(2026, 1, 1)).days + 1) * 96,
            strategies=["baseline"],
            out_root=tmp_path / "out",
            require_energyplus=True,
        )
    assert "No simulation started" in str(ei.value)
    assert "2026-07-03" in str(ei.value)


def test_elapsed_freezes_on_terminal():
    doc = {
        "started_at": "2026-08-12T20:00:00Z",
        "finished_at": "2026-08-12T20:00:10Z",
        "state": "failed",
    }
    assert elapsed_seconds(doc, now=1e12) == pytest.approx(10.0)


def test_stale_running_reconcile(tmp_path: Path):
    from eplus_gym_app.dsm_campaign import atomic_write_json, current_run_path

    doc = new_campaign_doc(
        run_id="r1",
        site=tmp_path,
        idf=tmp_path / "a.idf",
        idf_sha256="abc",
        begin="2026-01-01",
        end="2026-01-01",
        max_steps=96,
        n_days=1,
        strategies=["baseline"],
        weather_mode="AMY",
        jobs=[
            {
                "strategy_id": "baseline",
                "weather_kind": KIND_AMY,
                "epw": str(tmp_path / "a.epw"),
                "begin": "2026-01-01",
                "end": "2026-01-01",
                "max_steps": 96,
                "key": "baseline:AMY_OPEN_METEO",
            }
        ],
        epw_meta=[],
        preset="Peak day",
        peak_day="2026-01-01",
        supervisor_pid=0,
    )
    doc["state"] = "running"
    doc["heartbeat_at"] = "2020-01-01T00:00:00Z"
    doc["supervisor_pid"] = 0
    doc["child_pid"] = None
    # Bypass write_campaign so heartbeat is not refreshed.
    atomic_write_json(current_run_path(tmp_path), doc)
    out = reconcile_campaign(tmp_path)
    assert out["state"] == "failed"


def test_failure_leaves_last_dsm_run_unchanged(tmp_path: Path):
    last = tmp_path / "reports" / "eplus_gym" / "last_dsm_run.json"
    last.parent.mkdir(parents=True)
    last.write_text(json.dumps({"ok": True, "preset": "Peak day"}), encoding="utf-8")
    doc = {
        "run_id": "x",
        "state": "running",
        "completed_jobs": 0,
        "total_jobs": 1,
        "jobs": [],
    }
    mark_failed(tmp_path, doc, "boom")
    assert json.loads(last.read_text(encoding="utf-8"))["ok"] is True


def test_validate_job_rejects_design_day(tmp_path: Path):
    out = tmp_path / "job"
    out.mkdir()
    df = pd.DataFrame(
        {
            "facility_kw": [1.0] * 96,
            "day": ["1900-01-01"] * 96,
        }
    )
    pq = out / "traj_baseline.parquet"
    df.to_parquet(pq, index=False)
    with pytest.raises(ValueError, match="design-day"):
        validate_job_outputs(out, max_steps=96, begin="2026-01-26", end="2026-01-26")


def test_validate_job_increments_only_when_valid(tmp_path: Path):
    out = tmp_path / "job"
    out.mkdir()
    df = pd.DataFrame(
        {
            "facility_kw": [10.0] * 96,
            "day": ["2026-01-26"] * 96,
        }
    )
    df.to_parquet(out / "traj_x.parquet", index=False)
    gates = validate_job_outputs(out, max_steps=96, begin="2026-01-26", end="2026-01-26")
    assert gates["n_rows"] == 96
    assert gates["peak_kw"] == pytest.approx(10.0)


def test_energyplus_startup_error_preserves_fatal(tmp_path: Path):
    err = tmp_path / "episode-00000001-12345" / "eplusout.err"
    err.parent.mkdir(parents=True)
    err.write_text(
        "** Severe  ** Weather file does not include requested RunPeriod\n"
        "**  Fatal  ** EnergyPlus Terminated\n",
        encoding="utf-8",
    )

    class R:
        handle_error = "obs queue empty"
        sim_results = {"exit_code": 1}
        runner_config = type("C", (), {"output": str(tmp_path)})()

    diag = diagnose_startup_failure(R())
    assert diag["err_path"]
    assert "Fatal" in (diag["severe_or_fatal"] or "") or "Severe" in (
        diag["severe_or_fatal"] or ""
    )
    exc = EnergyPlusStartupError(
        diag["message"],
        exit_code=1,
        err_path=diag["err_path"],
        severe_or_fatal=diag["severe_or_fatal"],
        log_tail=diag["log_tail"],
    )
    assert "Fatal" in str(exc) or "Severe" in str(exc) or exc.severe_or_fatal


def test_publish_current_amy_updates_bundle(tmp_path: Path):
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    epw = _tiny_epw(weather / "madison_amy_202508_202608.epw", start=date(2025, 8, 1), days=10)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "site_ui_bundle_v1.json").write_text(
        json.dumps({"schema_version": "site_ui_bundle_v1", "epw": "eplus/weather/old.epw"}),
        encoding="utf-8",
    )
    meta = publish_current_amy(tmp_path, epw, {"kind": KIND_AMY})
    assert Path(meta["epw"]).name.startswith("madison_amy_")
    bundle = json.loads((reports / "site_ui_bundle_v1.json").read_text(encoding="utf-8"))
    assert bundle["epw"].endswith(epw.name)
    assert (weather / "amy_meta.json").is_file()
    inv = weather_inventory(tmp_path, published=tmp_path / bundle["epw"])
    assert inv.get("stale_bundle_epw") is False


def test_stale_bundle_detection(tmp_path: Path):
    weather = tmp_path / "eplus" / "weather"
    weather.mkdir(parents=True)
    new = _tiny_epw(weather / "madison_amy_202508_202608.epw", start=date(2025, 8, 1), days=3)
    old = _tiny_epw(weather / "madison_amy_202508_202607.epw", start=date(2025, 8, 1), days=2)
    (weather / "amy_meta.json").write_text(json.dumps({"epw": str(new)}), encoding="utf-8")
    inv = weather_inventory(tmp_path, published=old)
    assert inv["stale_bundle_epw"] is True
