"""Shared Studio workspace for uploads + agent artifacts.

Any AI agent works on this tree outside Streamlit; Studio is a dropzone + viewer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from wattlab.config import ARTIFACTS

_WORKSPACE_MD = """# WattLab Studio workspace

Shared between Streamlit Uploads and external AI agents.

```
uploads/dump/     # wattlab_dump_*.zip (vibe19 v3)
uploads/energy/   # energy-use zip/folder (campus.json + Haystack maps + Excel)
runs/             # twin / calibrate iterations (eplusout → browser 08 panes)
reports/          # scorecards, dashboard JSON, capital plans
```

Do not invent site ids or lat/lon — read campus.json / model_seed / MANIFEST.
"""


def workspace_root() -> Path:
    env = (
        os.environ.get("WATTLAB_STUDIO_WORKSPACE")
        or os.environ.get("WATTLab_WORKSPACE")
        or os.environ.get("WATTLAB_WORKSPACE")
        or ""
    ).strip()
    if env:
        return Path(env).expanduser().resolve()
    return (ARTIFACTS / "studio_workspace").resolve()


def ensure_workspace() -> Path:
    root = workspace_root()
    for sub in (
        root / "uploads" / "dump",
        root / "uploads" / "energy",
        root / "runs",
        root / "reports",
    ):
        sub.mkdir(parents=True, exist_ok=True)
    md = root / "WORKSPACE.md"
    if not md.is_file():
        md.write_text(_WORKSPACE_MD, encoding="utf-8")
    return root


def dump_upload_dir() -> Path:
    return ensure_workspace() / "uploads" / "dump"


def energy_upload_dir() -> Path:
    return ensure_workspace() / "uploads" / "energy"


def runs_dir() -> Path:
    return ensure_workspace() / "runs"


def reports_dir() -> Path:
    return ensure_workspace() / "reports"


def save_upload_bytes(kind: str, filename: str, data: bytes) -> Path:
    """Persist an uploaded zip. kind is ``dump`` or ``energy``."""
    if kind not in ("dump", "energy"):
        raise ValueError(f"kind must be dump|energy (got {kind!r})")
    safe = Path(filename).name or f"{kind}.zip"
    dest_dir = dump_upload_dir() if kind == "dump" else energy_upload_dir()
    dest = dest_dir / safe
    dest.write_bytes(data)
    return dest


def list_workspace_summary() -> dict[str, Any]:
    root = ensure_workspace()
    dumps = sorted((root / "uploads" / "dump").glob("*"))
    energy = sorted((root / "uploads" / "energy").glob("*"))
    runs = sorted((root / "runs").glob("*"))
    reports = sorted((root / "reports").glob("*"))
    return {
        "root": str(root),
        "dumps": [p.name for p in dumps if p.is_file() or p.is_dir()],
        "energy": [p.name for p in energy if p.is_file() or p.is_dir()],
        "runs": [p.name for p in runs],
        "reports": [p.name for p in reports],
    }


__all__ = [
    "dump_upload_dir",
    "energy_upload_dir",
    "ensure_workspace",
    "list_workspace_summary",
    "reports_dir",
    "runs_dir",
    "save_upload_bytes",
    "workspace_root",
]
