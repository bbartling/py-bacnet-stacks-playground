from __future__ import annotations

import hashlib
import json
import os
import shutil
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Unsafe ZIP member path: {member.filename!r}")
        archive.extractall(destination)


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "vibe23-lbnl-b59/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
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


def download_dataset(data_dir: Path, force: bool = False) -> dict:
    raw = data_dir / "raw"
    package = raw / "dryad_D1N33Q.zip"
    release_dir = raw / "dryad_release"
    telemetry_dir = raw / "building_59"

    if force:
        for path in (package, release_dir, telemetry_dir):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

    if not package.exists():
        _download(DRYAD_DOWNLOAD_URL, package)
    if not release_dir.exists():
        safe_extract(package, release_dir)

    discovered = {path.name for path in release_dir.rglob("*") if path.is_file()}
    missing = sorted(EXPECTED_RELEASE_FILES - discovered)
    if missing:
        raise FileNotFoundError("Dryad package missing expected files: " + ", ".join(missing))

    building_zip = _find_unique(release_dir, "Building_59.zip")
    if not telemetry_dir.exists():
        safe_extract(building_zip, telemetry_dir)

    manifest = {
        "schema": "vibe23.dataset_acquisition.v1",
        "doi": DATASET_DOI,
        "url": DRYAD_DOWNLOAD_URL,
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": {"path": str(package), "bytes": package.stat().st_size, "sha256": sha256_file(package)},
        "building_zip": {"path": str(building_zip), "bytes": building_zip.stat().st_size, "sha256": sha256_file(building_zip)},
        "telemetry_root": str(telemetry_dir),
        "release_files": sorted(EXPECTED_RELEASE_FILES),
    }
    (raw / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
