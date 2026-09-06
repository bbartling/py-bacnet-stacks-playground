"""Unit tests for the Render EnergyPlus worker HTTP client (mocked)."""
from __future__ import annotations

import io
import json
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
