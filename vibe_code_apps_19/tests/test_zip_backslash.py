"""Regression: Windows PowerShell ``Compress-Archive`` zips use backslash paths.

Those archives store folder markers like ``BUILDING_X\\AHU_1\\`` which
``ZipInfo.is_dir()`` does not recognize (it only checks for a trailing ``/``).
Before the fix, the marker was extracted as a zero-byte *file*, and every real
file under that folder then failed with ``[Errno 20] Not a directory`` (ENOTDIR)
on Linux/Docker.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.multi_zip import ZipPart, load_package_from_zip_parts
from app.package_io import (
    PackageError,
    _is_zip_dir,
    extract_package_zip,
    load_package_zip,
    wipe_workdir,
)
from tests.package_fixtures import minimal_sidecar_json


def _hist(n: int = 3) -> str:
    rows = ["timestamp_utc,fan_status,oa_t"]
    for i in range(n):
        rows.append(f"2024-06-01T12:{i:02d}:00Z,1,70")
    return "\n".join(rows)


def _manifest() -> str:
    return json.dumps(
        {
            "schema_version": "openfdd_package_v1",
            "building_id": "BUILDING_X",
            "grid_minutes": 5,
            "timezone": "UTC",
        }
    )


def _compress_archive_style_zip() -> bytes:
    """Backslash separators everywhere + explicit trailing-backslash dir markers.

    Modern ``zipfile`` normalizes ``\\`` to ``/`` when *writing*, so we write a
    normal zip (stored, uncompressed) and then rewrite the filename bytes in the
    local + central headers — exactly what a Compress-Archive zip looks like on
    the wire. Contents contain no path substrings, so replacement is safe.
    """
    files = {
        "BUILDING_X/manifest.json": _manifest(),
        "BUILDING_X/AHU_1/history_wide.csv": _hist(),
        "BUILDING_X/AHU_1/column_map.json": minimal_sidecar_json(),
        "BUILDING_X/VAV/VAV_1/history_wide.csv": _hist(),
        "BUILDING_X/VAV/VAV_1/column_map.json": minimal_sidecar_json(
            equip_type="vav", points={"zone-air-temp": "zone-air-temp"}
        ),
    }
    dir_markers = [
        "BUILDING_X/",
        "BUILDING_X/AHU_1/",
        "BUILDING_X/VAV/",
        "BUILDING_X/VAV/VAV_1/",
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for marker in dir_markers:
            info = zipfile.ZipInfo(marker)
            info.external_attr = 0o40775 << 16  # dir bits, like Compress-Archive
            zf.writestr(info, b"")
        for name, content in files.items():
            zf.writestr(name, content)
    raw = buf.getvalue()
    # Longest names first so shorter prefixes don't clobber substrings.
    for name in sorted([*files, *dir_markers], key=len, reverse=True):
        raw = raw.replace(name.encode(), name.replace("/", "\\").encode())
    return raw


def test_fixture_zip_really_has_backslash_names():
    data = _compress_archive_style_zip()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        # Archive must still be readable end-to-end after the byte rewrite
        for info in infos:
            zf.read(info)
    assert infos, "fixture zip is empty"
    # ``filename`` gets normalized on Windows readers; ``orig_filename`` is the
    # raw stored name — that is what a Linux/Docker deploy sees in ``filename``.
    raw_names = [i.orig_filename for i in infos]
    assert all("\\" in n for n in raw_names)
    assert not any("/" in n for n in raw_names)


def test_is_zip_dir_recognizes_backslash_markers():
    import os

    back = zipfile.ZipInfo("placeholder")
    back.filename = "BUILDING_X\\AHU_1\\"
    plain_file = zipfile.ZipInfo("placeholder")
    plain_file.filename = "BUILDING_X\\AHU_1\\history_wide.csv"
    if os.path.altsep is None:
        # POSIX (Linux/Docker deploy target): stdlib misses backslash markers —
        # the reason this bug existed.
        assert not back.is_dir()
    assert _is_zip_dir(zipfile.ZipInfo("BUILDING_X/AHU_1/"))
    assert _is_zip_dir(back)
    assert not _is_zip_dir(plain_file)


def test_extract_compress_archive_zip_no_enotdir():
    workdir = extract_package_zip(_compress_archive_style_zip())
    try:
        root = workdir / "BUILDING_X"
        assert (root / "manifest.json").is_file()
        assert (root / "AHU_1").is_dir()
        assert (root / "AHU_1" / "history_wide.csv").is_file()
        assert (root / "VAV" / "VAV_1" / "history_wide.csv").is_file()
        # Dir markers must not have been written as zero-byte files
        assert not (root / "AHU_1").is_file()
        assert not (root / "VAV").is_file()
    finally:
        wipe_workdir(workdir)


def test_load_package_zip_compress_archive_style():
    result = load_package_zip(_compress_archive_style_zip())
    try:
        assert "AHU_1" in result.frames
    finally:
        wipe_workdir(result.workdir)


def test_multi_zip_part_with_backslashes():
    parts = [ZipPart(name="building_part1.zip", data=_compress_archive_style_zip())]
    result = load_package_from_zip_parts(parts)
    try:
        assert "AHU_1" in result.frames
    finally:
        wipe_workdir(result.workdir)


def test_enotdir_style_failure_reports_package_error_with_hint(tmp_path, monkeypatch):
    """If extraction still hits an OSError, users get a PackageError with a hint."""
    import app.package_io as pio

    def _boom(target, entry_name):
        raise NotADirectoryError(20, "Not a directory", str(target))

    monkeypatch.setattr(pio, "_ensure_parent_dir", _boom)
    with pytest.raises(PackageError) as ei:
        pio.extract_package_zip(_compress_archive_style_zip())
    assert "Zip extraction failed" in str(ei.value)
    assert "Compress-Archive" in str(ei.value)
