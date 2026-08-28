#!/usr/bin/env python3
"""Supervisory-style Streamlit console for Phase 1 wire tests + Phase 2/3 roadmap."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "captures"
BINARY = ROOT / "target/release/serial-wire-test"
RUN_STATE = CAPTURES / ".wire_test_run.json"
PID_FILE = CAPTURES / ".wire_test.pid"

BAUD_RATES = [9600, 19200, 38400, 57600, 76800, 115200]
DEFAULT_PORT_A = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0"
DEFAULT_PORT_B = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0"

# Metasys / Niagara / PXC style targets (MS/TP supervisory); Phase 1 maps physical-layer analogs.
HEALTH_TARGETS = [
    ("Token rotation time (TRT)", "< 300 ms", "Phase 2 MS/TP", "—", "Token ring not exercised in Phase 1"),
    ("Lost tokens", "≈ 0", "missing + stale", "—", "Phase 1: timeout / dropped peer frames"),
    ("CRC / checksum errors", "< 1% frames", "corrupt + parser_rejected", "—", "Phase 1: bad CRC on private envelope"),
    ("Good frame count", "monotonic ↑", "peer envelopes OK", "—", "Both directions combined"),
    ("Round-trip time (RTT)", "< 300 ms typical", "latency mean", "—", "ReadProperty RTT in Phase 2"),
    ("Bus utilization", "20–50%", "estimated %", "—", "From bytes on wire vs baud × elapsed"),
]


@dataclass
class HealthCell:
    label: str
    value: str
    target: str
    state: str  # ok | warn | bad | na


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_run_state(data: dict[str, Any]) -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    RUN_STATE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_run_state() -> dict[str, Any] | None:
    return load_json(RUN_STATE)


def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def current_pid() -> int | None:
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if pid_running(pid):
                return pid
        except (OSError, ValueError):
            pass
    state = read_run_state()
    if state and "pid" in state:
        pid = int(state["pid"])
        if pid_running(pid):
            return pid
    return None


def stop_test() -> str:
    pid = current_pid()
    if pid is None:
        return "No running test."
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        return f"Stop failed: {e}"
    PID_FILE.unlink(missing_ok=True)
    return f"Sent SIGTERM to PID {pid}"


def ensure_release_binary() -> tuple[bool, str]:
    if BINARY.is_file():
        return True, str(BINARY)
    st.info("Building release binary (first time may take ~30s)…")
    proc = subprocess.run(
        ["cargo", "build", "--release", "-p", "serial-wire-test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False, proc.stderr[-2000:] if proc.stderr else "cargo build failed"
    return BINARY.is_file(), str(BINARY)


def in_dialout() -> bool:
    try:
        groups = subprocess.check_output(["id", "-nG"], text=True).split()
    except (OSError, subprocess.CalledProcessError):
        return False
    return "dialout" in groups


def start_test(
    port_a: str,
    port_b: str,
    baud: int,
    rounds: int,
    max_payload: int,
    seed: int,
    report_name: str,
) -> tuple[bool, str]:
    if current_pid() is not None:
        return False, "A test is already running. Stop it first."

    ok, bin_msg = ensure_release_binary()
    if not ok:
        return False, f"Binary missing: {bin_msg}"

    if not in_dialout():
        return False, (
            "User not in `dialout` group — run `sudo usermod -aG dialout $USER` "
            "then `newgrp dialout` or open a new login session."
        )

    CAPTURES.mkdir(parents=True, exist_ok=True)
    report_path = CAPTURES / report_name
    live_path = CAPTURES / f"{report_path.stem}-live.json"
    log_path = CAPTURES / f"{report_path.stem}.log"

    cmd = [
        str(BINARY),
        "--port-a",
        port_a,
        "--port-b",
        port_b,
        "--baud",
        str(baud),
        "--rounds",
        str(rounds),
        "--max-payload",
        str(max_payload),
        "--seed",
        str(seed),
        "--report",
        str(report_path),
    ]

    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    save_run_state(
        {
            "pid": proc.pid,
            "cmd": cmd,
            "report": str(report_path),
            "live": str(live_path),
            "log": str(log_path),
            "started_at": time.time(),
            "baud": baud,
            "rounds": rounds,
        }
    )
    return True, f"Started PID {proc.pid} → `{report_path.name}` (live: `{live_path.name}`)"


def list_reports() -> list[Path]:
    if not CAPTURES.is_dir():
        return []
    return sorted(
        [p for p in CAPTURES.glob("wire-test*.json") if not p.name.endswith("-live.json")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def pct_errors(data: dict[str, Any]) -> float:
    ok = int(data.get("envelopes_ok_a_to_b", 0)) + int(data.get("envelopes_ok_b_to_a", 0))
    bad = (
        int(data.get("missing", 0))
        + int(data.get("corrupt", 0))
        + int(data.get("duplicate", 0))
        + int(data.get("parser_rejected", 0))
    )
    total = ok + bad
    return (100.0 * bad / total) if total else 0.0


def estimate_bus_load(data: dict[str, Any], baud: int) -> float:
    """Rough duty cycle: payload+ framing bytes transmitted both directions / line capacity."""
    elapsed_ms = max(int(data.get("elapsed_ms", 1)), 1)
    bytes_ab = int(data.get("payload_bytes_a_to_b", 0)) + int(data.get("payload_bytes_b_to_a", 0))
    # ~15 bytes overhead per envelope (preamble+hdr+crc) × 2 directions per round
    rounds = int(data.get("rounds_completed", 0))
    wire_bytes = bytes_ab + rounds * 30
    line_bps = baud * (elapsed_ms / 1000.0)
    if line_bps <= 0:
        return 0.0
    return min(100.0, 100.0 * (wire_bytes * 10) / line_bps)  # 10 bits/byte


def health_from_live(live: dict[str, Any], report: dict[str, Any] | None, baud: int) -> list[HealthCell]:
    merged = {**(report or {}), **live}
    b = int(merged.get("baud", baud))
    err_pct = pct_errors(merged)
    rtt = float(merged.get("latency_mean_a_to_b_ms", 0) + merged.get("latency_mean_b_to_a_ms", 0)) / 2.0
    if rtt == 0 and report:
        lat_ab = (report.get("latency_ms_a_to_b") or {}).get("mean_ms", 0)
        lat_ba = (report.get("latency_ms_b_to_a") or {}).get("mean_ms", 0)
        rtt = (float(lat_ab) + float(lat_ba)) / 2.0
    good = int(merged.get("envelopes_ok_a_to_b", 0)) + int(merged.get("envelopes_ok_b_to_a", 0))
    lost = int(merged.get("missing", 0)) + int(merged.get("stale", 0))
    crc = int(merged.get("corrupt", 0)) + int(merged.get("parser_rejected", 0))
    bus = estimate_bus_load(merged, b)

    def st(ok: bool, warn: bool = False) -> str:
        if ok:
            return "ok"
        if warn:
            return "warn"
        return "bad"

    return [
        HealthCell("Token rotation (TRT)", "—", "< 300 ms", "na"),
        HealthCell("Lost tokens / drops", str(lost), "≈ 0", st(lost == 0, lost < 3)),
        HealthCell("CRC / checksum errors", str(crc), "< 1% frames", st(crc == 0, err_pct < 1.0)),
        HealthCell("Good frames", f"{good:,}", "↑", st(good > 0)),
        HealthCell("Round-trip time", f"{rtt:.1f} ms", "< 300 ms", st(rtt < 300, rtt < 500)),
        HealthCell("Bus utilization (est.)", f"{bus:.1f}%", "20–50%", st(20 <= bus <= 50, bus < 80)),
    ]


def render_health_table(cells: list[HealthCell]) -> None:
    icon = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "na": "⚪"}
    rows = []
    for c in cells:
        rows.append(
            {
                "Status": icon.get(c.state, "⚪"),
                "Metric": c.label,
                "Current": c.value,
                "Healthy target": c.target,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_supervisory_header() -> None:
    st.markdown(
        """
        ### BACnet MS/TP Lab — Supervisory Console
        **Phase 1 (now):** physical RS-485 / FTDI path via Rust `serial-wire-test` — no BACnet framing yet.  
        **Phase 2:** `rusty-bacnet` MS/TP token, Who-Is, RP/RPM on this same bus.  
        **Phase 3:** Rust B/IP ↔ MS/TP router + production commissioning web (Axum, not Streamlit).
        """
    )


def tab_run_control() -> None:
    st.subheader("Run control — Rust hardware test")
    c1, c2 = st.columns(2)
    with c1:
        port_a = st.text_input("Port A (by-id)", value=DEFAULT_PORT_A)
        port_b = st.text_input("Port B (by-id)", value=DEFAULT_PORT_B)
        baud = st.selectbox("Baud rate", BAUD_RATES, index=BAUD_RATES.index(38400))
    with c2:
        preset = st.radio("Preset", ["Smoke 100", "Gate 10,000", "Custom"], horizontal=True)
        if preset == "Smoke 100":
            rounds = 100
            report_name = f"wire-test-smoke-{baud}.json"
        elif preset == "Gate 10,000":
            rounds = 10_000
            report_name = f"wire-test-{baud}.json"
        else:
            rounds = st.number_input("Rounds", 1, 1_000_000, 100)
            report_name = st.text_input("Report filename", value="wire-test-custom.json")
        max_payload = st.number_input("Max payload bytes", 0, 256, 256)
        seed = st.number_input("Seed", 0, 2**32 - 1, 1337)

    if not in_dialout():
        st.warning("Not in `dialout` — serial open will fail until you re-login or `newgrp dialout`.")

    pid = current_pid()
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("▶ Start wire test", type="primary", disabled=pid is not None):
            ok, msg = start_test(port_a, port_b, baud, int(rounds), int(max_payload), int(seed), report_name)
            (st.success if ok else st.error)(msg)
            st.rerun()
    with b2:
        if st.button("⏹ Stop", disabled=pid is None):
            st.warning(stop_test())
            st.rerun()
    with b3:
        if st.button("🔨 Build release binary"):
            ok, msg = ensure_release_binary()
            (st.success if ok else st.error)(msg)

    if pid:
        st.info(f"Running PID **{pid}** — switch to **Live trunk** tab (auto-refresh on).")
        state = read_run_state()
        if state:
            st.caption(f"Log: `{state.get('log', '?')}`")


def tab_live_trunk(auto: bool, refresh_s: int) -> None:
    st.subheader("Live trunk — physical layer (Phase 1 analog)")
    state = read_run_state()
    live_path = Path(state["live"]) if state and state.get("live") else CAPTURES / "wire-test-38400-live.json"
    if not live_path.is_file():
        # pick newest *-live.json
        lives = sorted(CAPTURES.glob("*-live.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if lives:
            live_path = lives[0]

    live = load_json(live_path)
    report_path = Path(state["report"]) if state and state.get("report") else None
    report = load_json(report_path) if report_path and report_path.is_file() else None
    baud = int((state or {}).get("baud", (report or {}).get("baud", 38400)))

    if not live:
        st.info("No live progress file yet — start a run from **Run control**.")
        return

    status = str(live.get("status", "unknown"))
    req = int(live.get("rounds_requested", 0))
    done = int(live.get("rounds_completed", 0))
    pct = done / req if req else 0.0
    st.progress(min(pct, 1.0), text=f"{done:,} / {req:,} rounds ({pct * 100:.1f}%) @ {baud} bps")

    cells = health_from_live(live, report, baud)
    render_health_table(cells)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("A→B OK", f"{live.get('envelopes_ok_a_to_b', 0):,}")
    m2.metric("B→A OK", f"{live.get('envelopes_ok_b_to_a', 0):,}")
    m3.metric("CRC-ish errors", int(live.get("corrupt", 0)) + int(live.get("parser_rejected", 0)))
    m4.metric("RTT mean ms", f"{(float(live.get('latency_mean_a_to_b_ms', 0)) + float(live.get('latency_mean_b_to_a_ms', 0))) / 2:.1f}")
    m5.metric("Elapsed", f"{int(live.get('elapsed_ms', 0)) / 1000:.1f}s")

    recent = live.get("recent_latency_ms") or []
    if recent:
        st.markdown("**Round-trip latency (RTT analog)** — Metasys-style read response time preview")
        st.line_chart({"RTT ms": recent})
        st.caption("Spikes > 500 ms on a short bench cable → check FTDI latency timer, USB hub, or CPU load.")

    st.caption(f"Live file: `{live_path}` · updated `{live.get('updated_utc', '?')}`")

    if auto and status == "running":
        time.sleep(refresh_s)
        st.rerun()


def tab_post_run() -> None:
    st.subheader("Post-run analysis")
    reports = list_reports()
    if not reports:
        st.info("No finished reports in `captures/` yet.")
        return
    pick = st.selectbox("Report", reports, format_func=lambda p: p.name)
    data = load_json(pick)
    if not data:
        return

    baud = int(data.get("baud", 38400))
    cells = health_from_live({}, data, baud)
    render_health_table(cells)

    c1, c2, c3 = st.columns(3)
    c1.metric("Status", str(data.get("status")))
    c2.metric("Peer frames", f"{int(data.get('envelopes_ok_a_to_b', 0)) + int(data.get('envelopes_ok_b_to_a', 0)):,}")
    c3.metric("Error rate", f"{pct_errors(data):.3f}%")

    lat_ab = data.get("latency_ms_a_to_b") or {}
    lat_ba = data.get("latency_ms_b_to_a") or {}
    st.markdown("**Latency distribution**")
    st.bar_chart(
        {
            "A→B": [lat_ab.get("min_ms"), lat_ab.get("mean_ms"), lat_ab.get("max_ms")],
            "B→A": [lat_ba.get("min_ms"), lat_ba.get("mean_ms"), lat_ba.get("max_ms")],
        }
    )

    with st.expander("Full JSON report"):
        st.json(data)


def tab_roadmap() -> None:
    st.subheader("Supervisory metric roadmap")
    st.markdown(
        """
        | Layer | Phase 1 (Streamlit + Rust wire test) | Phase 2 (`rusty-bacnet` MS/TP) | Phase 3 (Rust router + Axum UI) |
        |-------|--------------------------------------|--------------------------------|----------------------------------|
        | Token TRT / lost token | Physical RTT + drop counters only | Real token rotation, Max_Master | Router MS/TP port + per-trunk stats |
        | CRC / good frames | Private envelope CRC | MS/TP CRC-32 / header errors | Routed + MS/TP combined |
        | Bus load | Estimated from baud × bytes | MS/TP utilization | B/IP + MS/TP per port |
        | Application RTT | Envelope round-trip | Who-Is / RP / RPM | B/IP client → router → device |

        **Why Streamlit now, Rust web later:** Streamlit is ideal for lab commissioning on bensbench — start tests, tune baud,
        watch live JSON. The **production appliance** (Phase 3) should use a Rust Axum read-only status API + small HTML
        (per checkpoint 13 spec), same metrics Metasys/Niagara operators expect, without Python on the edge box.
        """
    )
    st.markdown("**Reference targets (field MS/TP supervisory)**")
    st.table(
        [
            {"Category": r[0], "Healthy": r[1], "Phase 1 analog": r[2], "Notes": r[4]}
            for r in HEALTH_TARGETS
        ]
    )


def main() -> None:
    st.set_page_config(
        page_title="BACnet MS/TP Lab — Supervisory",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_supervisory_header()

    st.sidebar.header("Console")
    auto = st.sidebar.checkbox("Auto-refresh live tab", value=True)
    refresh_s = st.sidebar.slider("Refresh interval (s)", 1, 15, 2)
    if pid := current_pid():
        st.sidebar.success(f"Test running (PID {pid})")
    else:
        st.sidebar.caption("Idle")

    tab_run, tab_live, tab_post, tab_map = st.tabs(
        ["Run control", "Live trunk", "Post-run", "Roadmap"]
    )
    with tab_run:
        tab_run_control()
    with tab_live:
        tab_live_trunk(auto, refresh_s)
    with tab_post:
        tab_post_run()
    with tab_map:
        tab_roadmap()


if __name__ == "__main__":
    main()
