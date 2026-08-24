from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DATASET_DOI = "10.7941/D1N33Q"
DRYAD_DOWNLOAD_URL = "https://datadryad.org/api/v2/datasets/doi%3A10.7941%2FD1N33Q/download"
EXPECTED_RELEASE_FILES = {
    "Building_59.zip",
    "data_description_table_3year_clean_data.xlsx",
    "metadata_Dryad_Bldg59.docx",
    "README_Dryad_Bldg59.txt",
}
MAX_ARCHIVE_ENTRIES = 10_000
MAX_EXPANDED_BYTES = 4 * 1024**3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(
    zip_path: Path,
    destination: Path,
    *,
    max_entries: int = MAX_ARCHIVE_ENTRIES,
    max_expanded_bytes: int = MAX_EXPANDED_BYTES,
) -> None:
    """Extract an ordinary ZIP without trusting member paths or metadata.

    Dryad publishes one wrapper ZIP containing ``Building_59.zip`` and that
    archive contains the large telemetry tree, so nested archives cannot be
    rejected globally.  Each extraction pass still rejects traversal,
    symlinks, duplicate/case-colliding names, excessive entry counts and an
    excessive declared expanded size.  Files are streamed explicitly; Python's
    broad ``extractall`` helper is intentionally not used.
    """
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > int(max_entries):
            raise ValueError(f"ZIP has {len(members)} entries; maximum is {max_entries}")
        expanded = sum(int(member.file_size) for member in members)
        if expanded > int(max_expanded_bytes):
            raise ValueError(f"ZIP declares {expanded} expanded bytes; maximum is {max_expanded_bytes}")
        seen: set[str] = set()
        for member in members:
            normalized = member.filename.replace("\\", "/")
            collision_key = normalized.rstrip("/").casefold()
            if collision_key in seen:
                raise ValueError(f"Duplicate/case-colliding ZIP member: {member.filename!r}")
            seen.add(collision_key)
            target = (destination / normalized).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Unsafe ZIP member path: {member.filename!r}")
            mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"ZIP symlink is not allowed: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def _remove_generated_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _extract_archive_atomic(zip_path: Path, destination: Path) -> None:
    """Publish a complete extraction or leave no destination behind."""
    if destination.exists():
        raise FileExistsError(f"Refuse to replace existing extraction without --force: {destination}")
    partial = destination.with_name(destination.name + ".partial")
    _remove_generated_path(partial)
    try:
        safe_extract(zip_path, partial)
        os.replace(partial, destination)
    finally:
        _remove_generated_path(partial)


def _download(url: str, destination: Path, *, bearer_token: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    headers = {"User-Agent": "vibe23-lbnl-b59/0.2", "Accept": "application/zip,application/octet-stream"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        try:
            response = urllib.request.urlopen(request, timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError(
                    "Dryad rejected the automated download. Set VIBE23_DRYAD_BEARER_TOKEN for an "
                    "authorized API request, or download the published release manually and use "
                    "--source-release. No credentials are stored in the manifest."
                ) from exc
            raise
        with response, partial.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()


def _find_unique(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one {name!r} under {root}; found {len(matches)}")
    return matches[0]


def _stage_manual_release(source: Path, release_dir: Path) -> str:
    """Copy a manually downloaded Dryad release into the ignored raw area."""
    if source.is_dir():
        for name in EXPECTED_RELEASE_FILES:
            candidate = source / name
            if not candidate.is_file():
                raise FileNotFoundError(f"Manual release directory is missing {name!r}")
            shutil.copy2(candidate, release_dir / name)
        return "manual_release_directory"
    if not source.is_file() or source.suffix.lower() != ".zip":
        raise FileNotFoundError("--source-release must be a Dryad release directory or ZIP")
    # A full Dryad download is an outer ZIP.  A user may instead download the
    # large Building_59.zip and the three small metadata files beside it.
    with zipfile.ZipFile(source) as archive:
        names = {Path(info.filename).name for info in archive.infolist() if not info.is_dir()}
    if "Building_59.zip" in names:
        safe_extract(source, release_dir)
        return "manual_full_release_zip"
    shutil.copy2(source, release_dir / "Building_59.zip")
    for name in EXPECTED_RELEASE_FILES - {"Building_59.zip"}:
        candidate = source.parent / name
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Manual Building_59.zip requires sibling metadata file {name!r}; "
                "download all four published Dryad files"
            )
        shutil.copy2(candidate, release_dir / name)
    return "manual_individual_release_files"


def download_dataset(
    data_dir: Path,
    force: bool = False,
    *,
    source_release: Path | None = None,
    download_url: str | None = None,
) -> dict:
    raw = data_dir / "raw"
    package = raw / "dryad_D1N33Q.zip"
    release_dir = raw / "dryad_release"
    telemetry_dir = raw / "building_59"

    if force:
        for path in (package, release_dir, telemetry_dir):
            _remove_generated_path(path)

    acquisition_mode = "cached"
    if source_release is not None:
        source_release = Path(source_release).resolve()
        release_root = release_dir.resolve()
        if source_release == release_root or release_root in source_release.parents:
            raise ValueError("--source-release must be outside the generated dryad_release directory")
        _remove_generated_path(release_dir)
        staging = release_dir.with_name(release_dir.name + ".partial")
        _remove_generated_path(staging)
        staging.mkdir(parents=True)
        try:
            acquisition_mode = _stage_manual_release(source_release, staging)
            os.replace(staging, release_dir)
        finally:
            _remove_generated_path(staging)
    else:
        if not package.exists():
            _download(
                download_url or os.environ.get("VIBE23_DRYAD_DOWNLOAD_URL", DRYAD_DOWNLOAD_URL),
                package,
                bearer_token=os.environ.get("VIBE23_DRYAD_BEARER_TOKEN"),
            )
            acquisition_mode = "dryad_api"
        if not release_dir.exists():
            _extract_archive_atomic(package, release_dir)
            acquisition_mode = "dryad_api"

    discovered = {path.name for path in release_dir.rglob("*") if path.is_file()}
    missing = sorted(EXPECTED_RELEASE_FILES - discovered)
    if missing:
        raise FileNotFoundError("Dryad package missing expected files: " + ", ".join(missing))

    building_zip = _find_unique(release_dir, "Building_59.zip")
    if not telemetry_dir.exists():
        _extract_archive_atomic(building_zip, telemetry_dir)

    manifest = {
        "schema": "vibe23.dataset_acquisition.v1",
        "doi": DATASET_DOI,
        "url": download_url or os.environ.get("VIBE23_DRYAD_DOWNLOAD_URL", DRYAD_DOWNLOAD_URL),
        "acquisition_mode": acquisition_mode,
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": (
            {"path": str(package), "bytes": package.stat().st_size, "sha256": sha256_file(package)}
            if package.exists()
            else None
        ),
        "building_zip": {"path": str(building_zip), "bytes": building_zip.stat().st_size, "sha256": sha256_file(building_zip)},
        "telemetry_root": str(telemetry_dir),
        "release_files": sorted(EXPECTED_RELEASE_FILES),
    }
    (raw / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
