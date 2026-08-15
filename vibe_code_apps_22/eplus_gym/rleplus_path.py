"""Locate airboxlab/rllib-energyplus without installing Ray/Pearl."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_VIBE22 = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[2]


def rleplus_roots() -> list[Path]:
    env = os.environ.get("RLEPLUS_ROOT", "").strip()
    cands = []
    if env:
        cands.append(Path(env))
    cands.extend(
        [
            _VIBE22 / "third_party" / "rllib-energyplus",
            _REPO / "third_party" / "rllib-energyplus",
            Path.home() / "Documents" / "rllib-energyplus" / ".worktrees" / "feat-generic-runner",
            Path.home() / "Documents" / "rllib-energyplus",
        ]
    )
    return cands


PINNED_GENERIC_RUNNER_SHA_PREFIX = "01c5dc7"


def find_rleplus_root() -> Path:
    env = os.environ.get("RLEPLUS_ROOT", "").strip()
    roots = [Path(env)] if env else rleplus_roots()
    generic: list[Path] = []
    any_root: list[Path] = []
    for root in roots:
        if not (root / "rleplus" / "env" / "energyplus.py").is_file():
            continue
        any_root.append(root.resolve())
        if (root / "rleplus" / "env" / "day_run.py").is_file():
            generic.append(root.resolve())
    if generic:
        root = generic[0]
        sha = rleplus_git_sha(root)
        if not sha or not str(sha).startswith(PINNED_GENERIC_RUNNER_SHA_PREFIX):
            raise FileNotFoundError(
                f"rllib-energyplus at {root} is not pinned to {PINNED_GENERIC_RUNNER_SHA_PREFIX} (got {sha})"
            )
        return root
    if env and any_root:
        raise FileNotFoundError(
            "RLEPLUS_ROOT is set but missing feat/generic-runner helpers "
            "(rleplus/env/day_run.py). Pin SHA 01c5dc7; do not use main 89a2426."
        )
    raise FileNotFoundError(
        "rllib-energyplus generic-runner (01c5dc7 / day_run.py) not found. "
        "Set RLEPLUS_ROOT or clone the feat/generic-runner worktree. "
        "Do not use origin/main a8993f0 or local main 89a2426."
    )


def rleplus_git_sha(root: Path | None = None) -> str | None:
    import subprocess

    try:
        path = Path(root) if root else find_rleplus_root()
    except FileNotFoundError:
        return None
    try:
        out = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def ensure_rleplus() -> Path:
    root = find_rleplus_root()
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root
