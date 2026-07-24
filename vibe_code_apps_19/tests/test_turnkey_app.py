"""Turnkey app test: AppTest every main section + live HTML smoke.

Validates the Streamlit frontend renders without exceptions across all
REQUIRED_MAIN_SECTIONS, then optionally launches a real Streamlit server and
checks HTTP 200 + expected HTML markers.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
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
    slider_labels = {
        str(getattr(widget, "label", "") or "")
        for widget in (at.sidebar.slider or [])
    }
    for expected in (
        "Supply-fan heat rise ΔTSF (GL36 default 2°F)",
        "MAT sensor error εMAT (GL36 default 5°F)",
        "VFD speed error εVFDSPD (GL36 default 5%)",
        "Mode-change suspension (GL36 default 30)",
    ):
        assert expected in slider_labels, (
            f"GL36 sidebar slider missing: {expected!r}; "
            f"found {len(slider_labels)} slider labels"
        )

    radio = _section_radio(at)
    assert radio is not None, "Main Section radio not found"

    for section in REQUIRED_MAIN_SECTIONS:
        radio.set_value(section)
        at.run()
        assert not at.exception, f"Section {section!r} raised: {list(at.exception)}"
        # Re-acquire radio after rerun
        radio = _section_radio(at)
        assert radio is not None, f"Section radio missing after {section!r}"
    assert "Energy Model" not in REQUIRED_MAIN_SECTIONS


def _weather_csv(hours: list[int] | None = None) -> str:
    hours = hours or [12, 13, 14, 15, 16, 17]
    lines = ["timestamp_utc,dry_bulb_f,relative_humidity_pct"]
    for h in hours:
        lines.append(f"2024-06-01T{h:02d}:00:00Z,72,50")
    return "\n".join(lines) + "\n"


def _equip_zip(
    path: Path,
    equipment: dict[str, tuple[str, str, dict[str, str]]],
) -> None:
    """Write a tiny package.

    equipment values: (equipType, history_csv, points_map)
    ``points_map`` maps cookbook role → CSV column name.
    """
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "MECH_COOL_B1",
                    "grid_minutes": 60,
                    "timezone": "UTC",
                    "weather": "weather/history_wide.csv",
                }
            ),
        )
        role_map = {
            eq_id: dict(points) for eq_id, (_et, _hist, points) in equipment.items()
        }
        zf.writestr(
            "session_config.json",
            json.dumps(
                {
                    "schema_version": "openfdd_session_v1",
                    "unit_system": "imperial",
                    "prefer_web_oat": True,
                    "role_map": role_map,
                }
            ),
        )
        for eq_id, (equip_type, hist, points) in equipment.items():
            zf.writestr(f"{eq_id}/history_wide.csv", hist)
            zf.writestr(
                f"{eq_id}/column_map.json",
                json.dumps({"equipType": equip_type, "points": points}),
            )
            cols = "col,point_role\n" + "".join(
                f"{col},{role}\n" for role, col in points.items()
            )
            zf.writestr(f"{eq_id}/columns.csv", cols)
        zf.writestr("weather/history_wide.csv", _weather_csv())
        zf.writestr(
            "weather/columns.csv",
            "col,description\ntimestamp_utc,UTC\ndry_bulb_f,F\nrelative_humidity_pct,pct\n",
        )


def _bootstrap_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zpath: Path
):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

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
    return at


def _main_text(at) -> str:
    chunks: list[str] = []
    for attr in ("markdown", "caption", "info", "warning", "text", "subheader"):
        for el in getattr(at.main, attr, []) or []:
            chunks.append(str(getattr(el, "value", "") or ""))
    for df_el in getattr(at.main, "dataframe", []) or []:
        val = getattr(df_el, "value", None)
        if val is None:
            val = getattr(df_el, "data", None)
        chunks.append(str(val))
    return "\n".join(chunks)


@pytest.mark.timeout(300)
def test_export_wattlab_dump_button(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Export section: 'Build WattLab dump (zip)' produces a zip with README_WATTLAB.md."""
    import io

    zpath = tmp_path / "dump_pkg.zip"
    _tiny_zip(zpath)
    at = _bootstrap_app(tmp_path, monkeypatch, zpath)
    assert not at.exception, f"Initial render exceptions: {list(at.exception)}"

    radio = _section_radio(at)
    assert radio is not None
    radio.set_value("Export")
    at.run()
    assert not at.exception, f"Export section exceptions: {list(at.exception)}"

    build = next((b for b in at.main.button if getattr(b, "key", "") == "wattlab_dump_build"), None)
    assert build is not None, "Build WattLab dump button missing on Export section"
    build.click()
    at.run()
    assert not at.exception, f"Dump build exceptions: {list(at.exception)}"

    dump = at.session_state["wattlab_dump_zip"]
    assert dump, "wattlab_dump_zip not stored in session_state"
    data, fname = dump
    assert fname.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
    assert "README_WATTLAB.md" in names
    assert "MANIFEST.json" in names
    assert "run_report.json" in names
    assert "model_seed.json" in names
    assert "sensor_stats_all.csv" in names
    assert "fdd_findings.csv" in names
    # Default Summary profile: shared telemetry, no Cartesian per-rule timeseries
    assert any(n.startswith("telemetry/") for n in names)
    assert not any(n.startswith("fdd_timeseries/") for n in names)
    # Bootstrap pointer files must not be inside the user download
    assert not any(n.startswith("streamlit_bootstrap") for n in names)


@pytest.mark.timeout(300)
def test_mech_cooling_zero_eligible_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """CHW pump alone is not compressor proof → required zero-device warning."""
    hist = (
        "timestamp_utc,chw_pump_status\n"
        "2024-06-01T12:00:00Z,0\n"
        "2024-06-01T13:00:00Z,1\n"
        "2024-06-01T14:00:00Z,1\n"
        "2024-06-01T15:00:00Z,0\n"
        "2024-06-01T16:00:00Z,0\n"
        "2024-06-01T17:00:00Z,0\n"
    )
    zpath = tmp_path / "pump_only.zip"
    _equip_zip(
        zpath,
        {
            "CHILLER_1": (
                "chwPlant",
                hist,
                {"chw-pump-status": "chw_pump_status"},
            )
        },
    )
    at = _bootstrap_app(tmp_path, monkeypatch, zpath)
    assert not at.exception, f"Initial render exceptions: {list(at.exception)}"
    radio = _section_radio(at)
    assert radio is not None
    radio.set_value("Overview")
    at.run()
    assert not at.exception, f"Overview exceptions: {list(at.exception)}"

    from app.charts import mech_cooling_zero_eligible_warning

    expected = mech_cooling_zero_eligible_warning(pd.DataFrame())
    assert expected is not None
    warnings = list(at.main.warning or []) or list(at.warning or [])
    assert warnings, "expected st.warning element for zero eligible compressors"
    warning_text = "\n".join(str(getattr(w, "value", "") or "") for w in warnings)
    assert expected in warning_text
    # Must not pass solely from caption/markdown that merely mentions compressor proof.
    captions = "\n".join(
        str(getattr(c, "value", "") or "") for c in (at.main.caption or [])
    )
    assert expected not in captions


@pytest.mark.timeout(300)
def test_mech_cooling_one_device_message_and_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """One running device explains device-hours equality; coverage shows normalized fields."""
    hist_on = (
        "timestamp_utc,chiller_status\n"
        "2024-06-01T12:00:00Z,0\n"
        "2024-06-01T13:00:00Z,1\n"
        "2024-06-01T14:00:00Z,1\n"
        "2024-06-01T15:00:00Z,0\n"
        "2024-06-01T16:00:00Z,0\n"
        "2024-06-01T17:00:00Z,0\n"
    )
    hist_off = (
        "timestamp_utc,chiller_status\n"
        "2024-06-01T12:00:00Z,0\n"
        "2024-06-01T13:00:00Z,0\n"
        "2024-06-01T14:00:00Z,0\n"
        "2024-06-01T15:00:00Z,0\n"
        "2024-06-01T16:00:00Z,0\n"
        "2024-06-01T17:00:00Z,0\n"
    )
    zpath = tmp_path / "one_active.zip"
    _equip_zip(
        zpath,
        {
            "CHILLER_2": (
                "chwPlant",
                hist_on,
                {"chiller-status": "chiller_status"},
            ),
            "CHILLER_1": (
                "chwPlant",
                hist_off,
                {"chiller-status": "chiller_status"},
            ),
        },
    )
    at = _bootstrap_app(tmp_path, monkeypatch, zpath)
    assert not at.exception, f"Initial render exceptions: {list(at.exception)}"
    radio = _section_radio(at)
    assert radio is not None
    radio.set_value("Overview")
    at.run()
    assert not at.exception, f"Overview exceptions: {list(at.exception)}"

    text = _main_text(at)
    assert "Only CHILLER_2 had observed compressor runtime during this period." in text
    assert "Total compressor device-hours therefore equal CHILLER_2 runtime." in text
    assert "No runtime observed" in text

    # Coverage table present with normalized human-facing labels / values.
    assert at.main.dataframe, "expected coverage/bins dataframes on Overview"
    joined = text.lower()
    for label in ("eligibility", "activity", "proof", "runtime"):
        assert label in joined

    # Proof-mode checkbox (existing selector) remains default True across Overview rerun.
    proof = next(
        (
            c
            for c in at.sidebar.checkbox
            if c.label == "Use mapped mechanical-cooling status proof"
        ),
        None,
    )
    assert proof is not None and proof.value is True
    radio = _section_radio(at)
    radio.set_value("Export")
    at.run()
    assert not at.exception

    # Export-profile selectbox defaults to Summary and persists across section reruns.
    profile_box = next(
        (s for s in at.main.selectbox if getattr(s, "label", "") == "Export profile"),
        None,
    )
    assert profile_box is not None
    assert profile_box.value == "Summary (default)"
    assert at.session_state["wattlab_export_profile"] == "summary"
    profile_box.set_value("Diagnostic")
    at.run()
    assert not at.exception
    assert at.session_state["wattlab_export_profile"] == "diagnostic"

    radio = _section_radio(at)
    radio.set_value("Overview")
    at.run()
    assert not at.exception
    radio = _section_radio(at)
    radio.set_value("Export")
    at.run()
    assert not at.exception
    profile_box = next(
        s for s in at.main.selectbox if getattr(s, "label", "") == "Export profile"
    )
    assert profile_box.value == "Diagnostic"
    assert at.session_state["wattlab_export_profile"] == "diagnostic"

    proof = next(
        c
        for c in at.sidebar.checkbox
        if c.label == "Use mapped mechanical-cooling status proof"
    )
    assert proof.value is True
    radio = _section_radio(at)
    radio.set_value("Overview")
    at.run()
    assert not at.exception
    assert "Only CHILLER_2 had observed compressor runtime during this period." in _main_text(at)


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
        env.get("VIBE19_WATTLAB_PYTHON") or sys.executable,
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
