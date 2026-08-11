"""Run identifiers and SHA-256 artifact provenance for tutorial notebooks."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def make_run_id(*, prefix: str = "vibe22") -> str:
    """UTC timestamp + short random suffix, e.g. vibe22_20260806T201500Z_a1b2c3."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}_{suffix}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def artifact_registry(
    paths: dict[str, Path | str],
    *,
    run_id: str,
) -> dict[str, Any]:
    """Map logical names → absolute path + sha256 (missing files noted)."""
    entries: dict[str, Any] = {}
    for name, p in paths.items():
        path = Path(p)
        if path.is_file():
            entries[name] = {
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        else:
            entries[name] = {"path": str(path.resolve()), "sha256": None, "missing": True}
    return {"run_id": run_id, "artifacts": entries}


def print_artifact_registry(reg: dict[str, Any]) -> None:
    print(f"run_id: {reg.get('run_id')}", flush=True)
    for name, info in (reg.get("artifacts") or {}).items():
        sha = info.get("sha256") or "MISSING"
        print(f"  {name}: {info.get('path')}", flush=True)
        print(f"    sha256={sha}", flush=True)


def stamp_card(card: dict[str, Any], *, run_id: str, hashes: dict[str, str] | None = None) -> dict[str, Any]:
    out = dict(card)
    out["run_id"] = run_id
    if hashes:
        out["artifact_sha256"] = hashes
    return out
