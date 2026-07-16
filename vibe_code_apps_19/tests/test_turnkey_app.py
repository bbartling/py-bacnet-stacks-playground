"""Turnkey app test: AppTest every main section + live HTML smoke.

Validates the Streamlit frontend renders without exceptions across all
REQUIRED_MAIN_SECTIONS (including Energy Model), then optionally launches a
real Streamlit server and checks HTTP 200 + expected HTML markers.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from app.dashboard_contract import REQUIRED_MAIN_SECTIONS


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _tiny_zip(path: Path) -> None:
    hist = "timestamp_utc,fan_status,oa_t,sat\n"
    for i in range(12):
        hist += f"2024-06-01T12:{i:02d}:00Z,1,70,55\n"
    wx = "timestamp_utc,dry_bulb_f,relative_humidity_pct\n"
    for i in range(12):
        wx += f"2024-06-01T12:{i:02d}:00Z,70,50\n"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "TURNKEY_B1",
                    "grid_minutes": 5,
                    "timezone": "UTC",
                    "weather": "weather/history_wide.csv",
                }
            ),
        )
        zf.writestr(
            "session_config.json",
            json.dumps(
                {
                    "schema_version": "openfdd_session_v1",
                    "unit_system": "imperial",
                    "prefer_web_oat": True,
                    "role_map": {
                        "AHU_1": {
                            "fan-status": "fan-status",
                            "outside-air-temp": "outside-air-temp",
                            "discharge-air-temp": "discharge-air-temp",
                        }
                    },
                }
            ),
        )
        zf.writestr("AHU_1/history_wide.csv", hist)
        zf.writestr(
            "AHU_1/column_map.json",
            json.dumps(
                {
                    "equipType": "ahu",
                    "points": {
                        "fan-status": "fan-status",
                        "outside-air-temp": "outside-air-temp",
                        "discharge-air-temp": "discharge-air-temp",
                    },
                }
            ),
        )
        zf.writestr(
            "AHU_1/columns.csv",
            "col,point_role\nfan_status,fan_status\noa_t,oa_t\nsat,sat\n",
        )
        zf.writestr("weather/history_wide.csv", wx)
        zf.writestr(
            "weather/columns.csv",
            "col,description\ntimestamp_utc,UTC\ndry_bulb_f,F\nrelative_humidity_pct,pct\n",
        )


def _section_radio(at):
    for r in at.main.radio:
        if (r.label or "") == "Section" or getattr(r, "key", None) == "main_section":
            return r
    # Fallback: horizontal main sections radio is often the first main radio
    if at.main.radio:
        return at.main.radio[0]
    return None


@pytest.mark.timeout(300)
def test_turnkey_apptest_all_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    zpath = tmp_path / "turnkey.zip"
    _tiny_zip(zpath)
    boot = {
        "schema_version": "openfdd_bootstrap_v1",
        "package_path": str(zpath.resolve()),
        "auto_run_rules": False,
        "session_config": {
            "schema_version": "openfdd_session_v1",
            "unit_system": "imperial",
            "prefer_web_oat": True,
        },
    }
    boot_path = tmp_path / "streamlit_bootstrap.json"
    boot_path.write_text(json.dumps(boot), encoding="utf-8")
    monkeypatch.setenv("VIBE19_BOOTSTRAP", str(boot_path))
    monkeypatch.setenv("VIBE19_BOOTSTRAP_SKIP_RULES", "1")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")
    monkeypatch.setenv("APP_MODE", "cloud")

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"Initial render exceptions: {list(at.exception)}"

    radio = _section_radio(at)
    assert radio is not None, "Main Section radio not found"

    for section in REQUIRED_MAIN_SECTIONS:
        radio.set_value(section)
        at.run()
        assert not at.exception, f"Section {section!r} raised: {list(at.exception)}"
        # Re-acquire radio after rerun
        radio = _section_radio(at)
        assert radio is not None, f"Section radio missing after {section!r}"

    # Energy Model should at least render a heading or WattLab message
    radio.set_value("Energy Model")
    at.run()
    assert not at.exception, f"Energy Model exceptions: {list(at.exception)}"
    # Soft check: no unexpected error widgets required — WattLab may be absent in CI


@pytest.mark.timeout(120)
def test_turnkey_live_html_smoke():
    """Launch streamlit headless; GET / and /_stcore/health."""
    pytest.importorskip("streamlit")
    port = _free_port()
    env = os.environ.copy()
    env.setdefault("VIBE19_BOOTSTRAP_SKIP_RULES", "1")
    env.setdefault("VIBE19_BROWSER_AUTOLOAD", "0")
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    # Avoid picking up a developer bootstrap that auto-runs a huge package
    env.pop("VIBE19_BOOTSTRAP", None)

    cmd = [
        env.get("VIBE19_WATTLAB_PYTHON") or "python",
        "-m",
        "streamlit",
        "run",
        str(ROOT / "streamlit_app.py"),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--browser.gatherUsageStats",
        "false",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    root_url = f"http://127.0.0.1:{port}/"
    try:
        deadline = time.time() + 60
        healthy = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"Streamlit exited early code={proc.returncode}: {out[-2000:]}")
            try:
                with urllib.request.urlopen(health_url, timeout=2) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    if resp.status == 200 and "ok" in body.lower():
                        healthy = True
                        break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        assert healthy, "Streamlit /_stcore/health never became ok"

        with urllib.request.urlopen(root_url, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            assert resp.status == 200
            # Streamlit shell markers
            assert "streamlit" in html.lower() or "root" in html.lower()
            assert len(html) > 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
