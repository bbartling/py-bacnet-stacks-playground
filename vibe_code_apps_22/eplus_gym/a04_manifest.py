"""Immutable A04 three-hash manifest. Never rewrite A04 bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from eplus_gym.a04_identity import A04_GIT_BLOB, A04_IDF_NAME, A04_SHA_CRLF, A04_SHA_LF

MANIFEST_REL = "models/eplus/a04_model_manifest.json"


class A04ManifestError(ValueError):
    """A04 identity failed closed."""


def sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_lf(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def verify_a04_bytes(data: bytes) -> dict[str, str]:
    crlf = sha256_raw(data)
    lf = sha256_lf(data)
    if crlf != A04_SHA_CRLF:
        raise A04ManifestError(f"A04 CRLF sha mismatch: {crlf}")
    if lf != A04_SHA_LF:
        raise A04ManifestError(f"A04 LF sha mismatch: {lf}")
    return {"sha256_crlf": crlf, "sha256_lf": lf, "git_blob": A04_GIT_BLOB}


def load_a04_model_manifest(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / MANIFEST_REL
    if not path.is_file():
        raise A04ManifestError(f"missing {MANIFEST_REL}")
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("sha256_crlf") != A04_SHA_CRLF:
        raise A04ManifestError("manifest CRLF hash is not the frozen A04 pin")
    if body.get("sha256_lf") != A04_SHA_LF:
        raise A04ManifestError("manifest LF hash is not the frozen A04 pin")
    if body.get("git_blob") != A04_GIT_BLOB:
        raise A04ManifestError("manifest git blob is not the frozen A04 pin")
    if body.get("idf_name") != A04_IDF_NAME:
        raise A04ManifestError("manifest idf_name is not canonical A04")
    return body
