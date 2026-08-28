#!/usr/bin/env python3
"""Streamlit dashboard for Phase 1 serial-wire-test reports and live progress."""

from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "captures"


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_reports() -> list[Path]:
    if not CAPTURES.is_dir():
        return []
    return sorted(CAPTURES.glob("wire-test*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def status_emoji(status: str) -> str:
    return {
        "passed": "✅",
        "running": "🔄",
        "failed": "❌",
        "interrupted": "⚠️",
    }.get(status, "❓")


def render_live(data: dict) -> None:
    status = str(data.get("status", "unknown"))
    st.subheader(f"{status_emoji(status)} Live progress — {status}")
    req = int(data.get("rounds_requested", 0) or 0)
    done = int(data.get("rounds_completed", 0) or 0)
    pct = (done / req) if req else 0.0
    st.progress(min(pct, 1.0), text=f"{done:,} / {req:,} rounds ({pct * 100:.1f}%)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("A→B ok", f"{data.get('envelopes_ok_a_to_b', 0):,}")
    c2.metric("B→A ok", f"{data.get('envelopes_ok_b_to_a', 0):,}")
    c3.metric("Errors", f"{int(data.get('missing', 0)) + int(data.get('corrupt', 0)) + int(data.get('duplicate', 0))}")
    c4.metric("Elapsed ms", f"{data.get('elapsed_ms', 0):,}")
    recent = data.get("recent_latency_ms") or []
    if recent:
        st.line_chart({"round-trip ms": recent})
    st.caption(f"Updated: {data.get('updated_utc', '?')} → final report: `{data.get('report_path', '?')}`")


def render_report(data: dict) -> None:
    status = str(data.get("status", "unknown"))
    st.subheader(f"{status_emoji(status)} Final report — {status}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rounds", f"{data.get('rounds_completed', 0):,} / {data.get('rounds_requested', 0):,}")
    c2.metric("Baud", data.get("baud", "?"))
    c3.metric("Reason", data.get("reason", ""))
    st.write(
        {
            "peer errors": {
                "missing": data.get("missing"),
                "corrupt": data.get("corrupt"),
                "duplicate": data.get("duplicate"),
                "stale": data.get("stale"),
            },
            "latency A→B mean ms": (data.get("latency_ms_a_to_b") or {}).get("mean_ms"),
            "latency B→A mean ms": (data.get("latency_ms_b_to_a") or {}).get("mean_ms"),
        }
    )
    failures = data.get("failures") or []
    if failures:
        st.error("Failures")
        st.json(failures)


def main() -> None:
    st.set_page_config(page_title="Wire test dashboard", layout="wide")
    st.title("Phase 1 wire test dashboard")
    st.caption("Watch `*-live.json` during a long run; browse finished reports in `captures/`.")

    st.sidebar.header("Sources")
    auto = st.sidebar.checkbox("Auto refresh", value=True)
    refresh_s = st.sidebar.slider("Refresh (seconds)", 1, 30, 2)

    reports = list_reports()
    live_default = CAPTURES / "wire-test-38400-live.json"
    if not live_default.is_file() and reports:
        live_default = CAPTURES / f"{reports[0].stem}-live.json"
    try:
        live_default_str = str(live_default.relative_to(ROOT))
    except ValueError:
        live_default_str = str(live_default)

    live_path = Path(st.sidebar.text_input("Live progress file", value=live_default_str))
    if not live_path.is_absolute():
        live_path = ROOT / live_path

    report_pick = st.sidebar.selectbox(
        "Final report",
        options=["(none)"] + [str(p.relative_to(ROOT)) for p in reports],
    )

    live = load_json(live_path)
    if live:
        render_live(live)
    else:
        st.info(f"No live file yet: `{live_path}` — start a run; progress updates every 10 rounds.")

    if report_pick != "(none)":
        report = load_json(ROOT / report_pick)
        if report:
            render_report(report)

    with st.expander("Raw JSON"):
        if live:
            st.json(live)
        if report_pick != "(none)":
            rep = load_json(ROOT / report_pick)
            if rep:
                st.json(rep)

    if auto:
        time.sleep(refresh_s)
        st.rerun()


if __name__ == "__main__":
    main()
