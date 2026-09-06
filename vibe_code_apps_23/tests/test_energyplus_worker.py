"""Unit tests for the Render EnergyPlus worker HTTP client (mocked)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from vibe23.energyplus_worker import (
    EnergyPlusWorkerError,
    ensure_worker_awake,
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


def test_ensure_worker_awake_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("EPLUS_WORKER_URL", "https://example.test")
    monkeypatch.setenv("EPLUS_WORKER_API_KEY", "secret")
    calls = {"n": 0}

    def fake_healthz(*, timeout: float = 60.0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise EnergyPlusWorkerError("sleeping")
        return {"ok": True, "energyplus_version": "26.1.0", "api_key_configured": True}

    from vibe23 import energyplus_worker as mod

    monkeypatch.setattr(mod, "healthz", fake_healthz)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    result = ensure_worker_awake(attempts=4, per_try_timeout=1.0, pause_seconds=0.0)
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
