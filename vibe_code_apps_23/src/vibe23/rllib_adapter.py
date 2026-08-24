"""Pinned-upstream checks for the future Building 59 EnergyPlus adapter.

This module does not import Ray, Gymnasium, or the EnergyPlus Python API.  It
verifies that an engineer-provided checkout is the exact upstream revision
reviewed for Vibe 23 and records the limitation that currently blocks a direct
multi-actuator Building 59 integration.
"""
from __future__ import annotations

import hashlib
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .grid import RLIB_ENERGYPLUS_PIN, RLIB_ENERGYPLUS_REPOSITORY

ADAPTER_INSPECTION_SCHEMA = "vibe23.rllib_energyplus_inspection.v1"
EXPECTED_PACKAGE_NAME = "rl-energyplus"
EXPECTED_PACKAGE_VERSION = "0.11.0"
REQUIRED_FILES = (
    "pyproject.toml",
    "rleplus/env/energyplus.py",
    "rleplus/examples/amphitheater/env.py",
    "rleplus/train/rllib.py",
)


class UpstreamInspectionError(ValueError):
    """The supplied checkout is missing, unpinned, or structurally unexpected."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise UpstreamInspectionError(f"Could not read git HEAD for {root}") from exc
    return result.stdout.strip().lower()


def inspect_rllib_energyplus_checkout(root: Path) -> dict[str, Any]:
    """Verify and hash the exact reviewed ``airboxlab/rllib-energyplus`` pin."""

    root = Path(root).resolve()
    if not root.is_dir():
        raise UpstreamInspectionError(f"Upstream checkout does not exist: {root}")
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise UpstreamInspectionError(f"Upstream checkout is missing required files: {missing}")
    head = _git_head(root)
    if head != RLIB_ENERGYPLUS_PIN:
        raise UpstreamInspectionError(
            f"Unreviewed rllib-energyplus revision {head!r}; expected {RLIB_ENERGYPLUS_PIN}"
        )
    try:
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"]
    except (KeyError, tomllib.TOMLDecodeError) as exc:
        raise UpstreamInspectionError("Unexpected upstream pyproject metadata") from exc
    name = str(metadata.get("name", ""))
    version = str(metadata.get("version", ""))
    if name != EXPECTED_PACKAGE_NAME or version != EXPECTED_PACKAGE_VERSION:
        raise UpstreamInspectionError(
            f"Unexpected upstream package identity {name!r} {version!r}; "
            f"expected {EXPECTED_PACKAGE_NAME!r} {EXPECTED_PACKAGE_VERSION!r}"
        )
    files = {
        relative: {"sha256": _sha256_file(root / relative), "bytes": (root / relative).stat().st_size}
        for relative in REQUIRED_FILES
    }
    return {
        "schema": ADAPTER_INSPECTION_SCHEMA,
        "repository": RLIB_ENERGYPLUS_REPOSITORY,
        "commit": head,
        "package_name": name,
        "package_version": version,
        "files": files,
        "grid_search_owner": "Vibe 23 deterministic enumeration and paired scoring",
        "building59_runtime_status": "BLOCKED_UNTIL_MODEL_AND_ACTUATOR_BINDINGS_EXIST",
        "reviewed_limitation": (
            "The pinned upstream runner accepts an actuator dictionary but applies only its first actuator. "
            "A tested Vibe 23 multi-actuator wrapper or narrowly scoped single-actuator experiment is required."
        ),
        "claim_boundary": "Inspection proves provenance only; it does not prove an EnergyPlus run or DSM result.",
    }
