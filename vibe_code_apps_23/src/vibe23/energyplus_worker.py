"""HTTP client for the Vibe 23 EnergyPlus Render worker."""
from __future__ import annotations

import io
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


class EnergyPlusWorkerError(RuntimeError):
    """Remote EnergyPlus worker failed or returned an unexpected response."""


def worker_configured() -> bool:
    return bool(os.environ.get("EPLUS_WORKER_URL", "").strip()) and bool(
        os.environ.get("EPLUS_WORKER_API_KEY", "").strip()
    )


def worker_base_url() -> str:
    return os.environ.get("EPLUS_WORKER_URL", "").strip().rstrip("/")


def worker_api_key() -> str:
    return os.environ.get("EPLUS_WORKER_API_KEY", "").strip()


def prefer_worker_backend() -> bool:
    """Decide whether run_residential_day should use the remote worker."""
    backend = os.environ.get("EPLUS_BACKEND", "auto").strip().lower() or "auto"
    if backend in {"worker", "remote", "render", "cloud"}:
        return worker_configured()
    if backend in {"local", "native"}:
        return False
    # auto / force: remote when configured and either forced or no native exe
    if os.environ.get("EPLUS_WORKER_FORCE", "").strip().lower() in {"1", "true", "yes"}:
        return worker_configured()
    from .energyplus import resolve_native_energyplus

    if resolve_native_energyplus() is not None:
        return False
    return worker_configured()


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 120.0,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        raise EnergyPlusWorkerError(f"{method} {url} -> HTTP {exc.code}: {body[:500]!r}") from exc


def healthz(*, timeout: float = 60.0) -> dict[str, Any]:
    _, body = _request("GET", f"{worker_base_url()}/healthz", timeout=timeout)
    return json.loads(body)


def _multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes]]) -> tuple[bytes, str]:
    boundary = "----vibe23WorkerBoundary7a3f"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode() + b"\r\n")
    for name, (filename, content) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        chunks.append(b"Content-Type: application/octet-stream\r\n\r\n")
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def submit_job(
    *,
    idf_path: Path,
    epw_path: Path,
    expand_objects: bool = True,
) -> dict[str, Any]:
    if not worker_configured():
        raise EnergyPlusWorkerError("EPLUS_WORKER_URL / EPLUS_WORKER_API_KEY not configured")
    body, content_type = _multipart(
        {"expand_objects": "true" if expand_objects else "false"},
        {
            "idf": (idf_path.name, idf_path.read_bytes()),
            "epw": (epw_path.name, epw_path.read_bytes()),
        },
    )
    headers = {
        "Authorization": f"Bearer {worker_api_key()}",
        "Content-Type": content_type,
    }
    _, raw = _request("POST", f"{worker_base_url()}/v1/jobs", headers=headers, data=body, timeout=180.0)
    return json.loads(raw)


def get_job(job_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {worker_api_key()}"}
    _, raw = _request("GET", f"{worker_base_url()}/v1/jobs/{job_id}", headers=headers, timeout=60.0)
    return json.loads(raw)


def download_results_zip(job_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {worker_api_key()}"}
    _, raw = _request(
        "GET",
        f"{worker_base_url()}/v1/jobs/{job_id}/results",
        headers=headers,
        timeout=180.0,
    )
    return raw


def wait_for_job(
    job_id: str,
    *,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 960.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    payload: dict[str, Any] = {}
    while time.time() < deadline:
        payload = get_job(job_id)
        if payload.get("status") in {"succeeded", "failed"}:
            return payload
        time.sleep(poll_seconds)
    raise EnergyPlusWorkerError(f"timed out waiting for job {job_id}")


def extract_results_zip(zip_bytes: bytes, output_dir: Path) -> None:
    """Unpack worker results.zip into output_dir.

    Render worker archives use ``output/`` as the zip root (``make_archive(..., base_dir=\"output\")``).
    Flatten that prefix so callers find ``eplusout.csv`` directly under ``output_dir``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(output_dir)
    nested = output_dir / "output"
    if nested.is_dir():
        for child in nested.iterdir():
            target = output_dir / child.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(child), str(target))
        nested.rmdir()


def run_day_via_worker(
    *,
    idf_path: Path,
    epw_path: Path,
    output_dir: Path,
    expand_objects: bool = True,
    timeout_seconds: float = 960.0,
) -> dict[str, Any]:
    """Submit → poll → download → extract. Returns job metadata."""
    started = time.perf_counter()
    created = submit_job(idf_path=idf_path, epw_path=epw_path, expand_objects=expand_objects)
    job_id = str(created["job_id"])
    meta = wait_for_job(job_id, timeout_seconds=timeout_seconds)
    zip_bytes = download_results_zip(job_id)
    extract_results_zip(zip_bytes, output_dir)
    meta = dict(meta)
    meta["worker_job_id"] = job_id
    meta["worker_wall_seconds"] = round(time.perf_counter() - started, 3)
    (output_dir / "worker_job.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


__all__ = [
    "EnergyPlusWorkerError",
    "extract_results_zip",
    "get_job",
    "healthz",
    "prefer_worker_backend",
    "run_day_via_worker",
    "submit_job",
    "wait_for_job",
    "worker_configured",
]
