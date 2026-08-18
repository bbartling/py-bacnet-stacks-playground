"""Hostile ZIP ingest: fail closed, wipe only the failing session workspace."""

from __future__ import annotations

import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from app.package_io import (
    BROWSER_UNCOMPRESSED_MB,
    BROWSER_UPLOAD_MB,
    DEFAULT_SINGLE_FILE_MB,
    PackageCaps,
    PackageError,
    ExtractionBudget,
    effective_package_caps,
    extract_package_zip,
    load_package_zip,
    wipe_workdir,
)
from app.session_workspace import package_dir, session_root
from tests.package_fixtures import ensure_sidecar_files

ROOT = Path(__file__).resolve().parents[1]


def _hist(n: int = 3) -> str:
    rows = ["timestamp_utc,fan_status,oa_t"]
    for i in range(n):
        rows.append(f"2024-06-01T12:{i:02d}:00Z,1,70")
    return "\n".join(rows) + "\n"


def _manifest(**kw) -> str:
    base = {
        "schema_version": "openfdd_package_v1",
        "building_id": "SEC_1",
        "grid_minutes": 5,
        "timezone": "UTC",
    }
    base.update(kw)
    return json.dumps(base)


def _zip_bytes(files: dict[str, str | bytes]) -> bytes:
    files = ensure_sidecar_files(files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(name, data)
    return buf.getvalue()


def _valid_files() -> dict[str, str | bytes]:
    return {
        "manifest.json": _manifest(),
        "AHU_1/history_wide.csv": _hist(),
        "AHU_1/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\n",
    }


def _tiny_caps(**overrides) -> PackageCaps:
    base = dict(
        max_zip_bytes=10 * 1024 * 1024,
        max_uncompressed_bytes=10 * 1024 * 1024,
        max_entries=2000,
        max_equipment=100,
        max_single_file_bytes=80 * 1024 * 1024,
    )
    base.update(overrides)
    return PackageCaps(**base)


def test_valid_package_loads():
    result = load_package_zip(_zip_bytes(_valid_files()))
    try:
        assert "AHU_1" in result.frames
    finally:
        wipe_workdir(result.workdir)


def test_zip_slip_dotdot_rejected():
    z = _zip_bytes({"../evil.csv": "a,b\n1,2\n", **_valid_files()})
    with pytest.raises(PackageError, match="traversal|Absolute|rejected"):
        load_package_zip(z)


def test_absolute_unix_path_rejected():
    z = _zip_bytes({"/tmp/evil.csv": "a,b\n1,2\n", **_valid_files()})
    with pytest.raises(PackageError, match="Absolute|rejected"):
        load_package_zip(z)


def test_windows_drive_letter_rejected():
    z = _zip_bytes({"C:/Windows/evil.csv": "a,b\n1,2\n", **_valid_files()})
    with pytest.raises(PackageError, match="Absolute|rejected"):
        load_package_zip(z)


def test_symlink_entry_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", _manifest())
        zf.writestr("AHU_1/history_wide.csv", _hist())
        zf.writestr(
            "AHU_1/column_map.json",
            json.dumps({"equipType": "ahu", "points": {"fan-status": "fan-status"}}),
        )
        info = zipfile.ZipInfo("AHU_1/link.csv")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, b"target")
    with pytest.raises(PackageError, match="Symlink"):
        load_package_zip(buf.getvalue())


def test_duplicate_names_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", _manifest())
        zf.writestr("AHU_1/history_wide.csv", _hist())
        zf.writestr(
            "AHU_1/column_map.json",
            json.dumps({"equipType": "ahu", "points": {"fan-status": "fan-status"}}),
        )
        zf.writestr("AHU_1/history_wide.csv", _hist(n=4))
    with pytest.raises(PackageError, match="Duplicate"):
        load_package_zip(buf.getvalue())


def test_case_colliding_names_rejected():
    z = _zip_bytes(
        {
            **_valid_files(),
            "AHU_1/History_Wide.csv": _hist(n=4),
        }
    )
    with pytest.raises(PackageError, match="Duplicate|case-colliding"):
        load_package_zip(z)


def test_path_depth_rejected():
    deep = "/".join(["d"] * 9) + "/history_wide.csv"
    z = _zip_bytes({"manifest.json": _manifest(), deep: _hist()})
    with pytest.raises(PackageError, match="too deep"):
        load_package_zip(z)


def test_entry_cap_rejected(monkeypatch):
    monkeypatch.setenv("OPENFDD_MAX_ENTRIES", "3")
    files = {"manifest.json": _manifest()}
    for i in range(6):
        files[f"AHU_{i}/history_wide.csv"] = _hist()
    with pytest.raises(PackageError, match="too many items"):
        load_package_zip(_zip_bytes(files))


def test_declared_uncompressed_cap():
    caps = _tiny_caps(max_uncompressed_bytes=20)
    hist = _hist(n=40)
    with pytest.raises(PackageError, match="Uncompressed size exceeds"):
        load_package_zip(_zip_bytes({**_valid_files(), "AHU_1/history_wide.csv": hist}), caps=caps)


def test_streamed_bytes_cap_independent_of_declared(monkeypatch, tmp_path):
    monkeypatch.setattr("app.package_io._inspect_zip", lambda *a, **k: None)
    caps = _tiny_caps(max_uncompressed_bytes=30, max_single_file_bytes=10**9)
    with pytest.raises(PackageError, match="during extract"):
        extract_package_zip(_zip_bytes(_valid_files()), dest=tmp_path / "w", caps=caps)


def test_ratio_bomb_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _manifest())
        payload = b"0" * 50_000
        zf.writestr("AHU_1/history_wide.csv", payload)
        zf.writestr(
            "AHU_1/column_map.json",
            json.dumps({"equipType": "ahu", "points": {"fan-status": "fan-status"}}),
        )
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
        info = next(i for i in zf.infolist() if i.filename.endswith("history_wide.csv"))
        info.file_size = info.compress_size * 1000
        # ZipFile infolist is live; rewriting the central directory is hard.
        # Use inspect via a synthetic ZipInfo by extracting with a patched list.
    from app.package_io import _inspect_zip

    class _FakeZf:
        def infolist(self):
            info = zipfile.ZipInfo("AHU_1/history_wide.csv")
            info.file_size = 100_000
            info.compress_size = 10
            return [info]

    with pytest.raises(PackageError, match="compression ratio"):
        _inspect_zip(_FakeZf(), _tiny_caps())


def test_single_file_cap():
    caps = _tiny_caps(max_single_file_bytes=40)
    with pytest.raises(PackageError, match="single-file"):
        load_package_zip(_zip_bytes(_valid_files()), caps=caps)


def test_nested_zip_rejected():
    inner = _zip_bytes(
        {
            "history_wide.csv": _hist(),
            "column_map.json": json.dumps(
                {"equipType": "ahu", "points": {"fan-status": "fan-status"}}
            ),
        }
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", _manifest())
        zf.writestr("AHU_NEST.zip", inner)
    with pytest.raises(PackageError, match="Nested zip"):
        load_package_zip(buf.getvalue())


def test_html_js_rejected():
    z = _zip_bytes({**_valid_files(), "AHU_1/note.html": "<script>alert(1)</script>"})
    with pytest.raises(PackageError, match="Disallowed file type"):
        load_package_zip(z)


def test_failed_extract_wipes_dest(tmp_path):
    dest = tmp_path / "vibe19_failpkg"
    dest.mkdir()
    marker = dest / "should_go.txt"
    marker.write_text("x", encoding="utf-8")
    with pytest.raises(PackageError):
        extract_package_zip(_zip_bytes({"/tmp/evil.csv": "x"}), dest=dest)
    assert not dest.exists() or not any(dest.rglob("*"))


def test_session_a_intact_when_b_fails(tmp_path):
    sid_a = "a" * 32
    sid_b = "b" * 32
    dir_a = package_dir(sid_a, temp_dir=tmp_path)
    dir_b = package_dir(sid_b, temp_dir=tmp_path)
    result = load_package_zip(
        _zip_bytes(_valid_files()), dest=dir_a, protect=session_root(sid_a, temp_dir=tmp_path)
    )
    try:
        assert "AHU_1" in result.frames
        a_files = {p.name for p in dir_a.rglob("*") if p.is_file()}
        assert "manifest.json" in a_files
        with pytest.raises(PackageError):
            load_package_zip(
                _zip_bytes({"/tmp/evil.csv": "x", **_valid_files()}),
                dest=dir_b,
                protect=session_root(sid_b, temp_dir=tmp_path),
            )
        still = {p.name for p in dir_a.rglob("*") if p.is_file()}
        assert "manifest.json" in still
        assert "AHU_1" in result.frames
    finally:
        wipe_workdir(result.workdir)


def test_demo_package_still_loads():
    demo = ROOT / "data" / "demo_package_v1.zip"
    if not demo.is_file():
        pytest.skip("demo_package_v1.zip missing")
    result = load_package_zip(demo.read_bytes())
    try:
        assert result.frames
        assert result.manifest.schema_version == "openfdd_package_v1"
    finally:
        wipe_workdir(result.workdir)


def test_browser_caps_150_500_80(monkeypatch):
    for key in (
        "OPENFDD_MAX_ZIP_MB",
        "OPENFDD_MAX_UNCOMPRESSED_MB",
        "OPENFDD_MAX_SINGLE_FILE_MB",
    ):
        monkeypatch.delenv(key, raising=False)
    caps = effective_package_caps(for_browser_upload=True)
    assert caps.max_zip_mb == BROWSER_UPLOAD_MB == 150
    assert caps.max_uncompressed_mb == BROWSER_UNCOMPRESSED_MB == 500
    assert caps.max_single_file_mb == DEFAULT_SINGLE_FILE_MB == 80


def test_extraction_budget_consume_raises():
    budget = ExtractionBudget(max_uncompressed_bytes=10, max_single_file_bytes=8)
    with pytest.raises(PackageError, match="single-file"):
        budget.consume(9, filename="big.csv", file_written=9)


def test_malformed_session_config_is_package_error(tmp_path):
    z = _zip_bytes({**_valid_files(), "session_config.json": "{not-json"})
    with pytest.raises(PackageError, match="session_config"):
        load_package_zip(z)
