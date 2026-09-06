"""Unit tests for the Render EnergyPlus worker HTTP client (mocked)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from vibe23.energyplus_worker import (
    extract_results_zip,
    prefer_worker_backend,
    worker_configured,
)


def test_worker_configured_requires_url_and_key(monkeypatch):
    monkeypatch.delenv("EPLUS_WORKER_URL", raising=False)
    monkeypatch.delenv("EPLUS_WORKER_API_KEY", raising=False)
    assert worker_configured() is False
    monkeypatch.setenv("EPLUS_WORKER_URL", "https://example.test")
    assert worker_configured() is False
    monkeypatch.setenv("EPLUS_WORKER_API_KEY", "secret")
    assert worker_configured() is True


def test_prefer_worker_backend_modes(monkeypatch):
    monkeypatch.setenv("EPLUS_WORKER_URL", "https://example.test")
    monkeypatch.setenv("EPLUS_WORKER_API_KEY", "secret")
    monkeypatch.delenv("EPLUS_WORKER_FORCE", raising=False)

    monkeypatch.setenv("EPLUS_BACKEND", "worker")
    assert prefer_worker_backend() is True

    monkeypatch.setenv("EPLUS_BACKEND", "local")
    assert prefer_worker_backend() is False

    monkeypatch.setenv("EPLUS_BACKEND", "auto")
    monkeypatch.setenv("EPLUS_WORKER_FORCE", "1")
    assert prefer_worker_backend() is True


def test_probe_worker_status_lights(monkeypatch):
    monkeypatch.delenv("EPLUS_WORKER_URL", raising=False)
    monkeypatch.delenv("EPLUS_WORKER_API_KEY", raising=False)
    from vibe23 import energyplus_worker as mod

    red = mod.probe_worker_status()
    assert red["light"] == "red"
    assert red["label"] == "unconfigured"

    monkeypatch.setenv("EPLUS_WORKER_URL", "https://example.test")
    monkeypatch.setenv("EPLUS_WORKER_API_KEY", "secret")

    ticks = {"t": 0.0}

    def tick():
        cur = ticks["t"]
        ticks["t"] += 0.2
        return cur

    def slow_tick():
        cur = ticks["t"]
        ticks["t"] += 6.0
        return cur

    def fast_ok(*, timeout: float = 60.0):
        return {"ok": True, "energyplus_version": "26.1.0"}

    monkeypatch.setattr(mod, "healthz", fast_ok)
    monkeypatch.setattr(mod.time, "perf_counter", tick)
    ticks["t"] = 0.0
    live = mod.probe_worker_status(quick_timeout=2.5)
    assert live["light"] == "green"
    assert live["label"] == "live"

    monkeypatch.setattr(mod.time, "perf_counter", slow_tick)
    ticks["t"] = 0.0
    starting = mod.probe_worker_status(quick_timeout=10.0)
    assert starting["light"] == "yellow"
    assert starting["label"] == "starting"

    def boom(*, timeout: float = 60.0):
        raise mod.EnergyPlusWorkerError("connection refused")

    monkeypatch.setattr(mod, "healthz", boom)
    monkeypatch.setattr(mod.time, "perf_counter", tick)
    ticks["t"] = 0.0
    sleeping = mod.probe_worker_status(quick_timeout=2.5)
    assert sleeping["light"] == "red"
    assert sleeping["label"] == "sleeping"


def test_ensure_worker_awake_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("EPLUS_WORKER_URL", "https://example.test")
    monkeypatch.setenv("EPLUS_WORKER_API_KEY", "secret")
    calls = {"n": 0}
    from vibe23 import energyplus_worker as mod

    def fake_healthz(*, timeout: float = 60.0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise mod.EnergyPlusWorkerError("sleeping")
        return {"ok": True, "energyplus_version": "26.1.0", "api_key_configured": True}

    monkeypatch.setattr(mod, "healthz", fake_healthz)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    result = mod.ensure_worker_awake(attempts=4, per_try_timeout=1.0, pause_seconds=0.0)
    assert result["ok"] is True
    assert result["awake"] is True
    assert result["attempt"] == 3
    assert result["woke_from_sleep"] is True


def test_extract_results_zip_flattens_output_prefix(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("output/eplusout.csv", "Date/Time,x\n")
        zf.writestr("output/eplusout.err", "ok\n")
    dest = tmp_path / "run"
    extract_results_zip(buf.getvalue(), dest)
    assert (dest / "eplusout.csv").is_file()
    assert (dest / "eplusout.err").is_file()
    assert not (dest / "output").exists()


def test_extract_results_zip_accepts_flat_archive(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("eplusout.csv", "Date/Time,x\n")
    dest = tmp_path / "run"
    extract_results_zip(buf.getvalue(), dest)
    assert (dest / "eplusout.csv").read_text(encoding="utf-8").startswith("Date/Time")
