"""Require a supported OpenFDD wheel and expose provenance for the engineering bundle."""

from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def installed_open_fdd_path() -> str:
    try:
        import open_fdd

        return str(Path(open_fdd.__file__).resolve())
    except Exception:
        return "(open_fdd import failed)"

MIN_OPEN_FDD = (4, 4, 0)
MAX_OPEN_FDD_MAJOR = 5
MIN_OPEN_FDD_SPEC = ">=4.4.0,<5"

_APP_ROOT = Path(__file__).resolve().parents[1]


class OpenFddVersionError(RuntimeError):
    """Installed open-fdd is missing or outside the supported range."""


def _parse_pep440_major_minor_patch(raw: str) -> tuple[int, int, int]:
    head = str(raw).strip().split("+", 1)[0].split(".dev", 1)[0]
    parts = head.split(".")
    nums: list[int] = []
    for part in parts[:3]:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        nums.append(int(digits or "0"))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def installed_open_fdd_version() -> str:
    try:
        return version("open-fdd")
    except PackageNotFoundError as exc:
        raise OpenFddVersionError(
            f"open-fdd is not installed. Install open-fdd[reporting]{MIN_OPEN_FDD_SPEC}."
        ) from exc


def require_supported_open_fdd() -> str:
    """Refuse stale host wheels (3.0.1 / 4.3.0) and future major 5+."""
    ver = installed_open_fdd_version()
    path = installed_open_fdd_path()
    parsed = _parse_pep440_major_minor_patch(ver)
    if parsed[0] >= MAX_OPEN_FDD_MAJOR:
        raise OpenFddVersionError(
            f"open-fdd {ver} at {path} is too new (need <{MAX_OPEN_FDD_MAJOR})."
        )
    if parsed < MIN_OPEN_FDD:
        raise OpenFddVersionError(
            f"open-fdd {ver} at {path} is too old. Need {MIN_OPEN_FDD_SPEC} "
            "(do not use host 3.0.1 or 4.3.0)."
        )
    try:
        from open_fdd import __version__ as runtime
    except Exception as exc:  # pragma: no cover
        raise OpenFddVersionError(f"open-fdd import failed ({path}): {exc}") from exc
    if str(runtime).split("+", 1)[0] != ver.split("+", 1)[0]:
        raise OpenFddVersionError(
            f"open-fdd import version {runtime!r} does not match installed {ver!r} at {path}."
        )
    return ver


def application_git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_APP_ROOT.parent), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        return out.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def role_map_hash(role_map: dict[str, Any] | None) -> str | None:
    if not role_map:
        return None
    import hashlib

    try:
        from open_fdd.catalog import dumps_canonical

        blob = dumps_canonical({"role_map": role_map}).encode("utf-8")
    except Exception:
        import json

        blob = json.dumps(role_map, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def source_package_hash(path: str | Path | None) -> tuple[str | None, str | None]:
    if not path:
        return None, None
    p = Path(path)
    ident = p.name if p.exists() else str(path)
    if not p.is_file():
        return ident, None
    import hashlib

    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return ident, h.hexdigest()


def build_provenance(
    *,
    timezone: str | None = None,
    grid_interval_minutes: float | None = None,
    role_map: dict[str, Any] | None = None,
    source_path: str | None = None,
    export_profile: str = "summary",
) -> dict[str, Any]:
    from datetime import datetime, timezone as tz

    from open_fdd import manifest as ofdd_manifest

    require_supported_open_fdd()
    doc = ofdd_manifest()
    src_id, src_hash = source_package_hash(source_path)
    missing: list[str] = []
    py_sha = doc.get("git_revision") or doc.get("open_fdd_python_git_sha")
    if not py_sha:
        missing.append("open_fdd_python_git_sha")
    app_sha = application_git_sha()
    if not app_sha:
        missing.append("streamlit_application_git_sha")
    rust_ver = doc.get("rust_engine_version")
    if rust_ver is None:
        missing.append("rust_engine_version")
    cat_hash = doc.get("rule_catalog_hash")
    if not cat_hash:
        missing.append("rule_catalog_hash")
    cfg_hash = doc.get("effective_config_hash")
    if not cfg_hash:
        missing.append("effective_config_hash")
    if src_hash is None:
        missing.append("source_package_hash")

    return {
        "open_fdd_python_version": doc.get("open_fdd_python_version") or installed_open_fdd_version(),
        "open_fdd_python_git_sha": py_sha,
        "streamlit_application_git_sha": app_sha,
        "rust_engine_version": rust_ver,
        "bundle_schema_version": "openfdd_engineering_bundle_v1",
        "legacy_schema_version": "wattlab_dump_v3",
        "rule_catalog_hash": cat_hash,
        "effective_config_hash": cfg_hash,
        "rule_catalog_version": doc.get("rule_catalog_version"),
        "catalog_schema_version": doc.get("catalog_schema_version"),
        "source_package_identifier": src_id,
        "source_package_hash": src_hash,
        "export_timestamp": datetime.now(tz.utc).isoformat(),
        "timezone": timezone,
        "grid_interval_minutes": grid_interval_minutes,
        "selected_role_map_hash": role_map_hash(role_map),
        "export_profile": export_profile,
        "provenance_incomplete": bool(missing),
        "provenance_missing": missing,
    }
