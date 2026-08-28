#!/usr/bin/env python3
"""Supervisory Streamlit console for Phase 1 wire tests + Phase 2/3 roadmap."""

from __future__ import annotations

import json
import os
import pwd
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "captures"
BINARY = ROOT / "target/release/serial-wire-test"
MSTP_PROBE = ROOT / "target/release/mstp-probe"
MSTP_DEVICE = ROOT / "target/release/mstp-mini-device"
LAUNCHER = ROOT / "scripts/launch_serial_wire_test.sh"
RUN_STATE = CAPTURES / ".wire_test_run.json"
PID_FILE = CAPTURES / ".wire_test.pid"
MSTP_DEVICE_PID = CAPTURES / ".mstp_device.pid"
MSTP_ACCEPTANCE_REPORT = CAPTURES / "mstp-acceptance.json"

BAUD_RATES = [9600, 19200, 38400, 57600, 76800, 115200]
DEFAULT_PORT_A = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0"
DEFAULT_PORT_B = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0"
REPORT_NAME_RE = re.compile(r"^wire-test[-\w.]+\.json$")

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


def init_session_state() -> None:
    st.session_state.setdefault("flash", None)
    st.session_state.setdefault("live_mtime", 0.0)
    st.session_state.setdefault("live_snapshot", None)


def flash_message() -> None:
    msg = st.session_state.pop("flash", None)
    if not msg:
        return
    level, text = msg
    if level == "success":
        st.success(text)
    elif level == "error":
        st.error(text)
    elif level == "warning":
        st.warning(text)
    else:
        st.info(text)


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


def clear_run_artifacts(*, keep_live: bool = True) -> None:
    PID_FILE.unlink(missing_ok=True)
    if RUN_STATE.is_file():
        RUN_STATE.unlink(missing_ok=True)
    if not keep_live:
        for path in CAPTURES.glob("*-live.json"):
            path.unlink(missing_ok=True)


def reconcile_run_state() -> None:
    """Drop stale PID files and run state when the child process is gone."""
    pid = None
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    if pid is None:
        state = read_run_state()
        if state and "pid" in state:
            try:
                pid = int(state["pid"])
            except (TypeError, ValueError):
                pass
    if pid is not None and not pid_running(pid):
        PID_FILE.unlink(missing_ok=True)
        state = read_run_state()
        if state and int(state.get("pid", -1)) == pid:
            state["pid"] = None
            state["ended_at"] = time.time()
            save_run_state(state)


def current_pid() -> int | None:
    reconcile_run_state()
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if pid_running(pid):
                return pid
        except (OSError, ValueError):
            pass
    state = read_run_state()
    if state and state.get("pid") is not None:
        try:
            pid = int(state["pid"])
            if pid_running(pid):
                return pid
        except (TypeError, ValueError):
            pass
    return None


def stop_test(*, force: bool = False) -> str:
    pid = current_pid()
    if pid is None:
        if force:
            clear_run_artifacts()
            return "Cleared stale run state (no live process)."
        return "No running test."
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            if force:
                clear_run_artifacts()
                return f"Process gone; cleared state ({e})."
            return f"Stop failed: {e}"
    PID_FILE.unlink(missing_ok=True)
    state = read_run_state()
    if state:
        state["pid"] = None
        state["stopped_at"] = time.time()
        save_run_state(state)
    return f"Sent SIGTERM to process group for PID {pid}"


def ensure_release_binary(*, quiet: bool = False) -> tuple[bool, str]:
    if BINARY.is_file() and MSTP_PROBE.is_file() and MSTP_DEVICE.is_file():
        return True, str(BINARY)
    if not quiet:
        st.info("Building release binaries (first time may take ~60s)…")
    proc = subprocess.run(
        ["cargo", "build", "--release", "-p", "serial-wire-test", "-p", "mstp-probe", "-p", "mstp-mini-device"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False, proc.stderr[-2000:] if proc.stderr else "cargo build failed"
    ok = BINARY.is_file() and MSTP_PROBE.is_file() and MSTP_DEVICE.is_file()
    return ok, str(BINARY) if ok else "build finished but binaries missing"


def in_dialout() -> bool:
    try:
        groups = subprocess.check_output(["id", "-nG"], text=True).split()
    except (OSError, subprocess.CalledProcessError):
        return False
    return "dialout" in groups


def member_of_dialout() -> bool:
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or pwd.getpwuid(os.getuid()).pw_name
    try:
        line = subprocess.check_output(["getent", "group", "dialout"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    members = [m.strip() for m in line.split(":")[-1].split(",") if m.strip()]
    return user in members


def port_access_ok(path: str) -> bool:
    p = Path(path)
    return p.exists() and os.access(p, os.R_OK | os.W_OK)


def serial_access_status(port_a: str, port_b: str) -> tuple[str, str]:
    missing = [p for p in (port_a, port_b) if not Path(p).exists()]
    if missing:
        return "error", f"Adapter not found: `{missing[0]}` — check USB / by-id path."

    denied = [p for p in (port_a, port_b) if not port_access_ok(p)]
    if not denied:
        return "ok", "Serial ports readable — Start can open both adapters."

    if member_of_dialout():
        if in_dialout():
            return "error", (
                f"Ports denied despite active `dialout`: `{denied[0]}`. "
                "Check cable, another process holding the port, or udev rules."
            )
        return "warn", (
            "You are in `dialout` but this Streamlit session is not — Start will "
            "re-launch the Rust test via `sg dialout` (no `newgrp` needed)."
        )

    return "error", (
        "Serial ports not writable — run `sudo usermod -aG dialout $USER`, "
        "then restart this dashboard (sidebar → **Reload UI**)."
    )


def safe_report_path(report_name: str) -> Path | None:
    name = Path(report_name).name
    if not REPORT_NAME_RE.match(name):
        return None
    return CAPTURES / name


def build_wire_cmd(
    port_a: str,
    port_b: str,
    baud: int,
    rounds: int,
    max_payload: int,
    seed: int,
    report_path: Path,
) -> list[str]:
    wire_args = [
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
    if port_access_ok(port_a) and port_access_ok(port_b):
        return [str(BINARY), *wire_args]
    if LAUNCHER.is_file():
        return [str(LAUNCHER), str(BINARY), *wire_args]
    return [str(BINARY), *wire_args]


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

    ok, bin_msg = ensure_release_binary(quiet=True)
    if not ok:
        return False, f"Binary missing: {bin_msg}"

    level, access_msg = serial_access_status(port_a, port_b)
    if level == "error":
        return False, access_msg

    report_path = safe_report_path(report_name)
    if report_path is None:
        return False, f"Invalid report filename `{report_name}` — use wire-test-*.json in captures/."

    CAPTURES.mkdir(parents=True, exist_ok=True)
    live_path = CAPTURES / f"{report_path.stem}-live.json"
    log_path = CAPTURES / f"{report_path.stem}.log"
    cmd = build_wire_cmd(port_a, port_b, baud, rounds, max_payload, seed, report_path)

    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    time.sleep(0.25)
    if proc.poll() is not None:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:] if log_path.is_file() else ""
        return False, f"Wire test exited immediately (code {proc.returncode}). Log tail:\n{tail}"

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
    st.session_state.live_mtime = 0.0
    st.session_state.live_snapshot = None
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
    elapsed_ms = max(int(data.get("elapsed_ms", 1)), 1)
    bytes_ab = int(data.get("payload_bytes_a_to_b", 0)) + int(data.get("payload_bytes_b_to_a", 0))
    rounds = int(data.get("rounds_completed", 0))
    wire_bytes = bytes_ab + rounds * 30
    line_bps = baud * (elapsed_ms / 1000.0)
    if line_bps <= 0:
        return 0.0
    return min(100.0, 100.0 * (wire_bytes * 10) / line_bps)


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


def resolve_live_paths() -> tuple[Path | None, Path | None, int]:
    state = read_run_state()
    live_path = Path(state["live"]) if state and state.get("live") else None
    report_path = Path(state["report"]) if state and state.get("report") else None
    if live_path is None or not live_path.is_file():
        lives = sorted(CAPTURES.glob("*-live.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        live_path = lives[0] if lives else None
    baud = int((state or {}).get("baud", 38400))
    return live_path, report_path, baud


def live_file_mtime(live_path: Path | None) -> float:
    if live_path and live_path.is_file():
        return live_path.stat().st_mtime
    return 0.0


def is_live_active(live: dict[str, Any] | None, pid: int | None) -> bool:
    if pid is not None:
        return True
    return live is not None and str(live.get("status")) == "running"


def render_health_table(cells: list[HealthCell]) -> None:
    icon = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "na": "⚪"}
    rows = [
        {
            "Status": icon.get(c.state, "⚪"),
            "Metric": c.label,
            "Current": c.value,
            "Healthy target": c.target,
        }
        for c in cells
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_live_panel(
    *,
    live_path: Path | None = None,
    report_path: Path | None = None,
    baud: int | None = None,
    heading: str = "Live trunk — physical layer",
) -> bool:
    if live_path is None:
        live_path, report_path, baud = resolve_live_paths()
    elif baud is None:
        _, report_path, baud = resolve_live_paths()

    live = load_json(live_path) if live_path and live_path.is_file() else None
    report = load_json(report_path) if report_path and report_path.is_file() else None
    if baud is None:
        baud = int((report or live or {}).get("baud", 38400))

    if not live:
        return False

    st.markdown(f"#### {heading}")
    status = str(live.get("status", "unknown"))
    if status == "running":
        st.info("🔄 Test in progress — live JSON updates every ~10 rounds")
    elif status == "complete":
        st.success("✅ Run finished — final report written alongside live file.")

    req = int(live.get("rounds_requested", 0))
    done = int(live.get("rounds_completed", 0))
    pct = done / req if req else 0.0
    st.progress(min(pct, 1.0), text=f"{done:,} / {req:,} rounds ({pct * 100:.1f}%) @ {baud} bps")

    render_health_table(health_from_live(live, report, baud))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("A→B OK", f"{live.get('envelopes_ok_a_to_b', 0):,}")
    m2.metric("B→A OK", f"{live.get('envelopes_ok_b_to_a', 0):,}")
    m3.metric("CRC-ish errors", int(live.get("corrupt", 0)) + int(live.get("parser_rejected", 0)))
    m4.metric(
        "RTT mean ms",
        f"{(float(live.get('latency_mean_a_to_b_ms', 0)) + float(live.get('latency_mean_b_to_a_ms', 0))) / 2:.1f}",
    )
    m5.metric("Elapsed", f"{int(live.get('elapsed_ms', 0)) / 1000:.1f}s")

    recent = live.get("recent_latency_ms") or []
    if recent:
        st.markdown("**Round-trip latency (RTT)**")
        st.line_chart({"RTT ms": recent})
        st.caption("Spikes > 500 ms on a short bench cable → FTDI latency timer, USB hub, or CPU load.")

    if live_path:
        st.caption(f"Live file: `{live_path.name}` · updated `{live.get('updated_utc', '?')}`")
    return True


def render_supervisory_header() -> None:
    st.markdown(
        """
        ### BACnet MS/TP Lab — Supervisory Console
        **Phase 1:** physical RS-485 / FTDI path via Rust `serial-wire-test`.  
        **Phase 2:** `rusty-bacnet` MS/TP token, Who-Is, RP/RPM.  
        **Phase 3:** Rust B/IP ↔ MS/TP router + Axum commissioning web.
        """
    )


def render_lab_console(refresh_s: int) -> None:
    st.subheader("Lab console — run control + live trunk")

    c1, c2 = st.columns(2)
    with c1:
        port_a = st.text_input("Port A (by-id)", value=DEFAULT_PORT_A, key="port_a")
        port_b = st.text_input("Port B (by-id)", value=DEFAULT_PORT_B, key="port_b")
        baud = st.selectbox("Baud rate", BAUD_RATES, index=BAUD_RATES.index(38400), key="baud")
    with c2:
        preset = st.radio("Preset", ["Smoke 100", "Gate 10,000", "Custom"], horizontal=True, key="preset")
        if preset == "Smoke 100":
            rounds = 100
            report_name = f"wire-test-smoke-{baud}.json"
        elif preset == "Gate 10,000":
            rounds = 10_000
            report_name = f"wire-test-{baud}.json"
        else:
            rounds = st.number_input("Rounds", 1, 1_000_000, 100, key="rounds")
            report_name = st.text_input("Report filename", value="wire-test-custom.json", key="report_name")
        max_payload = st.number_input("Max payload bytes", 0, 256, 256, key="max_payload")
        seed = st.number_input("Seed", 0, 2**32 - 1, 1337, key="seed")

    access_level, access_msg = serial_access_status(port_a, port_b)
    if access_level == "ok":
        st.success(access_msg)
    elif access_level == "warn":
        st.warning(access_msg)
    else:
        st.error(access_msg)

    pid = current_pid()
    running = pid is not None

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("▶ Start wire test", type="primary", disabled=running, key="btn_start"):
        with st.status("Starting Rust wire test…", expanded=True) as run_status:
            run_status.write("Checking release binary…")
            ok, msg = start_test(
                port_a, port_b, baud, int(rounds), int(max_payload), int(seed), report_name
            )
            if ok:
                run_status.update(label="Wire test running", state="complete")
                st.session_state.flash = ("success", msg)
            else:
                run_status.update(label="Start failed", state="error")
                run_status.write(msg)
                st.session_state.flash = ("error", msg)

    if b2.button("⏹ Stop", disabled=not running, key="btn_stop"):
        st.session_state.flash = ("warning", stop_test())

    if b3.button("🧹 Clear stale state", key="btn_clear"):
        st.session_state.flash = ("info", stop_test(force=True))

    if b4.button("🔨 Build release", key="btn_build"):
        with st.status("Building serial-wire-test…", expanded=True) as build_status:
            ok, msg = ensure_release_binary(quiet=True)
            if ok:
                build_status.update(label="Release binary ready", state="complete")
                st.session_state.flash = ("success", msg)
            else:
                build_status.update(label="Build failed", state="error")
                build_status.write(msg)
                st.session_state.flash = ("error", msg)

    flash_message()

    st.divider()
    state = read_run_state()
    if running:
        st.caption(f"Running PID **{pid}** · log `{state.get('log', '?') if state else '?'}`")
    elif state and state.get("log"):
        with st.expander("Last run log tail"):
            log_path = Path(state["log"])
            if log_path.is_file():
                st.code(log_path.read_text(encoding="utf-8", errors="replace")[-4000:], language="text")
            else:
                st.caption("Log file missing.")

    live_path, report_path, resolved_baud = resolve_live_paths()
    live = load_json(live_path) if live_path else None
    if is_live_active(live, current_pid()):
        render_live_panel_auto(refresh_s)
    elif live:
        render_live_panel(live_path=live_path, report_path=report_path, baud=resolved_baud)
    else:
        st.caption("Press **Start** — progress, health table, and RTT chart appear here.")


@st.fragment(run_every=timedelta(seconds=1))
def render_live_panel_auto(refresh_s: int) -> None:
    reconcile_run_state()
    live_path, report_path, baud = resolve_live_paths()
    mtime = live_file_mtime(live_path)
    pid = current_pid()
    live = load_json(live_path) if live_path else None

    if mtime == st.session_state.live_mtime and st.session_state.live_snapshot and pid is not None:
        snap = st.session_state.live_snapshot
        st.markdown("#### Live trunk — physical layer")
        st.info(f"🔄 Running · PID {pid} · refresh when live file changes (~{refresh_s}s poll)")
        st.progress(snap["pct"], text=snap["progress_text"])
        st.caption(snap["caption"])
        return

    st.session_state.live_mtime = mtime
    if not render_live_panel(live_path=live_path, report_path=report_path, baud=baud):
        if pid is not None:
            st.caption("Waiting for first live JSON snapshot (~10 rounds)…")
        else:
            st.caption("Run ended — use **Reload UI** in the sidebar if metrics look stale.")
        return

    if live_path and live:
        req = int(live.get("rounds_requested", 0))
        done = int(live.get("rounds_completed", 0))
        pct = done / req if req else 0.0
        st.session_state.live_snapshot = {
            "pct": min(pct, 1.0),
            "progress_text": f"{done:,} / {req:,} rounds ({pct * 100:.1f}%) @ {baud} bps",
            "caption": f"Live file: `{live_path.name}` · updated `{live.get('updated_utc', '?')}`",
        }


def mstp_device_pid() -> int | None:
    if not MSTP_DEVICE_PID.is_file():
        return None
    try:
        pid = int(MSTP_DEVICE_PID.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if pid_running(pid) else None


def stop_mstp_device() -> str:
    pid = mstp_device_pid()
    if pid is None:
        MSTP_DEVICE_PID.unlink(missing_ok=True)
        return "No MS/TP mini-device running."
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)
    MSTP_DEVICE_PID.unlink(missing_ok=True)
    return f"Stopped mini-device PID {pid}"


def start_mstp_device(port_b: str, baud: int, mac: int = 1) -> tuple[bool, str]:
    if mstp_device_pid() is not None:
        return False, "Mini-device already running — stop it first."
    ok, msg = ensure_release_binary(quiet=True)
    if not ok:
        return False, msg
    level, access_msg = serial_access_status(DEFAULT_PORT_A, port_b)
    if level == "error":
        return False, access_msg
    cmd = [
        str(MSTP_DEVICE),
        "--serial",
        port_b,
        "--baud",
        str(baud),
        "--mac",
        str(mac),
        "--device-instance",
        "123001",
    ]
    if LAUNCHER.is_file() and not port_access_ok(port_b):
        cmd = [str(LAUNCHER), str(MSTP_DEVICE), *cmd[1:]]
    log_path = CAPTURES / "mstp-mini-device.log"
    CAPTURES.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    time.sleep(0.3)
    if proc.poll() is not None:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
        return False, f"Mini-device exited immediately:\n{tail}"
    MSTP_DEVICE_PID.write_text(str(proc.pid), encoding="utf-8")
    return True, f"Mini-device PID {proc.pid} on `{port_b}` (log: `{log_path.name}`)"


def run_mstp_loopback() -> tuple[bool, str]:
    ok, msg = ensure_release_binary(quiet=True)
    if not ok:
        return False, msg
    report = CAPTURES / "mstp-loopback.json"
    proc = subprocess.run(
        [str(MSTP_PROBE), "loopback", "--report", str(report), "--repeated-reads", "5"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr[-1500:] if proc.stderr else proc.stdout[-1500:]
        return False, f"Loopback acceptance failed:\n{detail}"
    data = load_json(report)
    status = (data or {}).get("status", "?")
    return status == "Passed", f"Loopback {status} → `{report.name}`"


def tab_mstp_phase2() -> None:
    st.subheader("Phase 2 — rusty-bacnet MS/TP")
    st.caption(
        "Loopback acceptance runs in-process (CI-safe). Hardware needs mini-device on Port B, "
        "then probe on Port A with A+/B-/REF wired."
    )

    c1, c2 = st.columns(2)
    with c1:
        port_a = st.text_input("Probe Port A (by-id)", value=DEFAULT_PORT_A, key="mstp_port_a")
        baud = st.selectbox("Baud", BAUD_RATES, index=BAUD_RATES.index(38400), key="mstp_baud")
    with c2:
        port_b = st.text_input("Device Port B (by-id)", value=DEFAULT_PORT_B, key="mstp_port_b")
        st.caption("Device MAC 1 · Probe MAC 0 · instance 123001")

    device_pid = mstp_device_pid()
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("▶ Start mini-device", disabled=device_pid is not None, key="mstp_start_dev"):
        with st.spinner("Launching mstp-mini-device…"):
            ok, msg = start_mstp_device(port_b, baud)
        st.session_state.flash = ("success" if ok else "error", msg)
    if b2.button("⏹ Stop mini-device", disabled=device_pid is None, key="mstp_stop_dev"):
        st.session_state.flash = ("warning", stop_mstp_device())
    if b3.button("🧪 Loopback acceptance", key="mstp_loopback"):
        with st.spinner("Running mstp-probe loopback (no USB)…"):
            ok, msg = run_mstp_loopback()
        st.session_state.flash = ("success" if ok else "error", msg)
    if b4.button("🔬 Hardware probe", key="mstp_hw_probe"):
        ok, bin_msg = ensure_release_binary(quiet=True)
        if not ok:
            st.session_state.flash = ("error", bin_msg)
        else:
            report = CAPTURES / "mstp-hardware.json"
            if LAUNCHER.is_file() and not port_access_ok(port_a):
                cmd = [str(LAUNCHER), str(MSTP_PROBE), "hardware", "--probe-serial", port_a, "--device-serial", port_b, "--report", str(report)]
            else:
                cmd = [
                    str(MSTP_PROBE),
                    "hardware",
                    "--probe-serial",
                    port_a,
                    "--device-serial",
                    port_b,
                    "--report",
                    str(report),
                ]
            with st.spinner("Running hardware acceptance (device must be up)…"):
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if proc.returncode == 0:
                st.session_state.flash = ("success", f"Hardware acceptance Passed → `{report.name}`")
            else:
                detail = proc.stderr[-1500:] if proc.stderr else proc.stdout[-1500:]
                st.session_state.flash = ("error", f"Hardware probe failed:\n{detail}")

    flash_message()

    for report_path in [CAPTURES / "mstp-loopback.json", CAPTURES / "mstp-hardware.json", MSTP_ACCEPTANCE_REPORT]:
        data = load_json(report_path)
        if data:
            st.markdown(f"**Last report:** `{report_path.name}` — **{data.get('status', '?')}**")
            st.dataframe(
                [
                    {
                        "Step": s.get("step"),
                        "OK": "✅" if s.get("ok") else "❌",
                        "Detail": s.get("detail"),
                        "ms": s.get("latency_ms"),
                    }
                    for s in data.get("steps", [])
                ],
                width="stretch",
                hide_index=True,
            )
            break


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
    render_health_table(health_from_live({}, data, baud))

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
        """
    )
    st.table(
        [
            {"Category": r[0], "Healthy": r[1], "Phase 1 analog": r[2], "Notes": r[4]}
            for r in HEALTH_TARGETS
        ]
    )


def render_sidebar() -> int:
    st.sidebar.header("Console")
    pid = current_pid()
    if pid:
        st.sidebar.success(f"Test running (PID {pid})")
    else:
        st.sidebar.caption("Idle")

    refresh_s = st.sidebar.slider("Live poll interval (s)", 1, 10, 2)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Session tools**")
    if st.sidebar.button("↻ Reload UI", key="sidebar_reload", width="stretch"):
        st.session_state.live_mtime = 0.0
        st.session_state.live_snapshot = None
        st.rerun()
    if st.sidebar.button("🧹 Clear run state", key="sidebar_clear", width="stretch"):
        st.session_state.flash = ("info", stop_test(force=True))
        st.rerun()
    st.sidebar.caption(
        "Dashboard: `./scripts/run_wire_dashboard.sh` (attach if already running). "
        "Restart: `./scripts/run_wire_dashboard.sh --restart`"
    )
    return refresh_s


def main() -> None:
    st.set_page_config(
        page_title="BACnet MS/TP Lab — Supervisory",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()
    reconcile_run_state()
    render_supervisory_header()
    refresh_s = render_sidebar()

    tab_lab, tab_mstp, tab_post, tab_map = st.tabs(["Lab console", "MS/TP Phase 2", "Post-run", "Roadmap"])
    with tab_lab:
        render_lab_console(refresh_s)
    with tab_mstp:
        tab_mstp_phase2()
    with tab_post:
        tab_post_run()
    with tab_map:
        tab_roadmap()


if __name__ == "__main__":
    main()
