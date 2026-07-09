"""Thin bridge from Python dashboard to local `fdd_cli` (Rust + DataFusion).

Use when open-fdd HTTP edge is unavailable. Set `RUST_FDD_USE_CLI=1` to prefer
this path for ingest / rule batch during migration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_APP_ROOT = _HERE.parent.parent
_RUST_ROOT = _APP_ROOT / "rust_fdd_core"
_DEFAULT_PARQUET = _APP_ROOT / ".cache" / "parquet"
_DEFAULT_RULES = _APP_ROOT / "sql_rules"


def cli_binary() -> Path | None:
    """Release binary if built, else None (caller may use `cargo run`)."""
    env = os.environ.get("RUST_FDD_CLI")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    release = _RUST_ROOT / "target" / "release" / "fdd_cli.exe"
    if release.is_file():
        return release
    release_unix = _RUST_ROOT / "target" / "release" / "fdd_cli"
    return release_unix if release_unix.is_file() else None


def is_available() -> bool:
    """True if fdd_cli binary exists or cargo workspace is present."""
    if cli_binary() is not None:
        return True
    return (_RUST_ROOT / "Cargo.toml").is_file() and shutil.which("cargo") is not None


def _run(args: list[str], *, timeout: float = 600.0) -> dict[str, Any]:
    bin_path = cli_binary()
    if bin_path is not None:
        cmd = [str(bin_path), *args]
        cwd = None
    else:
        cmd = ["cargo", "run", "-p", "fdd_cli", "--release", "--", *args]
        cwd = str(_RUST_ROOT)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout or "fdd_cli failed").strip(),
            "returncode": proc.returncode,
        }
    try:
        return {"ok": True, **json.loads(proc.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "raw": proc.stdout.strip()}


def validate(data_root: Path | str, building_id: str) -> dict[str, Any]:
    return _run(["validate", "--data-root", str(data_root), "--building", building_id])


def ingest(
    data_root: Path | str,
    building_id: str,
    *,
    out_dir: Path | str | None = None,
    timeout: float = 3600.0,
) -> dict[str, Any]:
    out = Path(out_dir or _DEFAULT_PARQUET)
    return _run(
        [
            "ingest",
            "--data-root",
            str(data_root),
            "--building",
            building_id,
            "--out",
            str(out),
        ],
        timeout=timeout,
    )


def run_rules(
    *,
    parquet_dir: Path | str | None = None,
    rules_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
    timeout: float = 600.0,
) -> dict[str, Any]:
    parquet = Path(parquet_dir or _DEFAULT_PARQUET)
    rules = Path(rules_dir or _DEFAULT_RULES)
    out = Path(out_dir or (_APP_ROOT / ".cache" / "rule_results"))
    return _run(
        [
            "run-rules",
            "--parquet",
            str(parquet),
            "--rules-dir",
            str(rules),
            "--out",
            str(out),
        ],
        timeout=timeout,
    )


def status() -> dict[str, Any]:
    """Summary for `/api/sidecar/status`."""
    bin_path = cli_binary()
    return {
        "available": is_available(),
        "cli_binary": str(bin_path) if bin_path else None,
        "rust_root": str(_RUST_ROOT),
        "parquet_default": str(_DEFAULT_PARQUET),
        "rules_dir": str(_DEFAULT_RULES),
        "enabled": os.environ.get("RUST_FDD_USE_CLI", "").strip() in ("1", "true", "yes"),
    }
