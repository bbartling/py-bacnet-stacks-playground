#!/usr/bin/env python
"""Smoke: Streamlit AppTest on the real site + optional 1-day live W2A."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))


def _apptest() -> int:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP / "eplus_gym_app" / "streamlit_app.py"))
    at.run(timeout=180)
    if at.exception:
        print("APPTEST_EXCEPTION", at.exception)
        return 2
    titles = [str(t.value) for t in at.title]
    print("TITLE", titles)
    assert any("Lakeside DSM" in t for t in titles)
    labels = " ".join(str(getattr(w, "label", "")) for w in list(at.radio) + list(at.selectbox))
    assert "IDF source" not in labels
    errs = [str(e.value) for e in at.error]
    print("ERRORS", errs or "none")
    warns = [str(w.value) for w in at.warning]
    print("WARNINGS", warns or "none")
    print("SELECTBOXES", [getattr(s, "label", "") for s in at.selectbox])
    print("METRICS", len(at.metric), "DATAFRAMES", len(at.dataframe))
    print("APPTEST_OK")
    return 0


def _live_day() -> int:
    from eplus_gym.simulate import run_rule_episode, trajectory_frame
    from eplus_native.idf_stage import patch_run_period
    from lakeside.paths import site_root

    site = site_root()
    src = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    if not epw.is_file():
        cands = list((site / "eplus" / "weather").glob("*.epw"))
        if not cands:
            print("NO_EPW")
            return 3
        epw = cands[0]
    out = site / "reports" / "eplus_gym" / "runs" / "smoke_a04_jan26"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    staged = out / "a04_jan26.idf"
    text = src.read_text(encoding="utf-8")
    text = patch_run_period(
        text,
        begin_month=1,
        begin_day=26,
        end_month=1,
        end_day=26,
        begin_year=2026,
        end_year=2026,
        name="SMOKE_JAN26",
    )
    staged.write_text(text, encoding="utf-8")
    print("LIVE_START", staged, epw)
    result = run_rule_episode(
        site_root=site,
        strategy_id="baseline",
        day="2026-01-26",
        mode="live",
        family="w2a",
        epw=epw,
        idf=staged,
        output=out,
        max_steps=96,
        verbose=True,
    )
    df = trajectory_frame(result)
    meta = result["meta"]
    print("LIVE_META", meta)
    print("LIVE_ROWS", len(df), "cols", list(df.columns))
    if "facility_kw" in df.columns:
        peak = float(df["facility_kw"].max())
        print("LIVE_PEAK_KW", peak, "KWH", float(df["facility_kw"].sum() * 0.25))
        if peak != peak:
            print("LIVE_PEAK_NAN")
            return 5
    elif "facility_j" in df.columns:
        print("LIVE_FACILITY_J_MAX", float(df["facility_j"].max()))
        return 5
    return 0 if len(df) > 0 else 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    rc = _apptest()
    if rc:
        return rc
    if args.live:
        return _live_day()
    print("APPTEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
