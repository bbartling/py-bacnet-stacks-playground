"""Uploads path resolution under Studio workspace (BUG-001)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattlab.studio.pages.uploads import _resolve_upload_path


def test_resolve_upload_path_relative_under_workspace(tmp_path: Path):
    dump = tmp_path / "uploads" / "dump"
    dump.mkdir(parents=True)
    target = dump / "wattlab_dump_X.zip"
    target.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    got = _resolve_upload_path("uploads/dump/wattlab_dump_X.zip", root=tmp_path)
    assert got == target.resolve()


def test_resolve_upload_path_absolute(tmp_path: Path):
    target = tmp_path / "abs.zip"
    target.write_bytes(b"x")
    got = _resolve_upload_path(str(target), root=tmp_path / "other")
    assert got == target.resolve()


def test_resolve_upload_path_missing_hints_workspace(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Studio workspace"):
        _resolve_upload_path("uploads/dump/missing.zip", root=tmp_path)
