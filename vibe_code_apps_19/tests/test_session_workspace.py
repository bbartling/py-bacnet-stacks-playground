"""Per-session workspace isolation for hosted Streamlit (no EnergyPlus)."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest

from app.session_workspace import (
    HEARTBEAT_NAME,
    ensure_session_id,
    exports_dir,
    package_dir,
    path_is_inside,
    session_root,
    sweep_stale_workspaces,
    touch_heartbeat,
    wipe_workspace,
    workspace_parent,
)


def _sid_state(sid: str | None = None) -> dict:
    state: dict = {}
    if sid is not None:
        state["session_id"] = sid
    return state


def test_two_session_identities_produce_different_workdirs(tmp_path: Path) -> None:
    id_a = ensure_session_id(_sid_state())
    id_b = ensure_session_id(_sid_state())
    assert id_a != id_b
    assert len(id_a) >= 32
    root_a = session_root(id_a, temp_dir=tmp_path)
    root_b = session_root(id_b, temp_dir=tmp_path)
    assert root_a != root_b
    assert root_a.parent == root_b.parent == workspace_parent(temp_dir=tmp_path)
    assert root_a.parent.name == "vibe19"
    assert package_dir(id_a, temp_dir=tmp_path) != package_dir(id_b, temp_dir=tmp_path)


def test_session_a_upload_does_not_alter_session_b(tmp_path: Path) -> None:
    id_a = "a" * 32
    id_b = "b" * 32
    pkg_a = package_dir(id_a, temp_dir=tmp_path)
    pkg_b = package_dir(id_b, temp_dir=tmp_path)
    marker = pkg_a / "A_ONLY.txt"
    marker.write_text("alice", encoding="utf-8")
    (pkg_b / "B_ONLY.txt").write_text("bob", encoding="utf-8")
    assert marker.read_text(encoding="utf-8") == "alice"
    assert not (pkg_b / "A_ONLY.txt").exists()
    assert not (pkg_a / "B_ONLY.txt").exists()


def test_wipe_session_a_leaves_session_b_intact(tmp_path: Path) -> None:
    id_a = "c" * 32
    id_b = "d" * 32
    root_a = session_root(id_a, temp_dir=tmp_path)
    root_b = session_root(id_b, temp_dir=tmp_path)
    (package_dir(id_a, temp_dir=tmp_path) / "gone.txt").write_text("x", encoding="utf-8")
    keep = package_dir(id_b, temp_dir=tmp_path) / "keep.txt"
    keep.write_text("stay", encoding="utf-8")
    wipe_workspace(root_a, session_id=id_a, temp_dir=tmp_path)
    assert not root_a.exists()
    assert keep.is_file()
    assert keep.read_text(encoding="utf-8") == "stay"


def test_wipe_refuses_workspace_parent(tmp_path: Path) -> None:
    parent = workspace_parent(temp_dir=tmp_path)
    parent.mkdir(parents=True, exist_ok=True)
    sentinel = parent / "not_a_session"
    sentinel.mkdir()
    (sentinel / "x.txt").write_text("nope", encoding="utf-8")
    wipe_workspace(parent, temp_dir=tmp_path)
    assert parent.is_dir()
    assert (sentinel / "x.txt").is_file()


def test_sweep_protects_active_unrelated_workspace(tmp_path: Path) -> None:
    id_active = "e" * 32
    id_stale = "f" * 32
    active = session_root(id_active, temp_dir=tmp_path)
    stale = session_root(id_stale, temp_dir=tmp_path)
    (package_dir(id_active, temp_dir=tmp_path) / "live.txt").write_text("live", encoding="utf-8")
    (package_dir(id_stale, temp_dir=tmp_path) / "old.txt").write_text("old", encoding="utf-8")
    touch_heartbeat(active)
    # Make stale look abandoned (heartbeat + dir mtime in the past).
    old = time.time() - 8 * 3600
    hb = stale / HEARTBEAT_NAME
    hb.write_text("stale", encoding="utf-8")
    import os

    os.utime(hb, (old, old))
    os.utime(stale, (old, old))
    removed = sweep_stale_workspaces(
        protect=active, max_age_sec=6 * 3600, temp_dir=tmp_path
    )
    assert removed >= 1
    assert (package_dir(id_active, temp_dir=tmp_path) / "live.txt").is_file()
    assert not stale.exists()


def test_path_is_inside_rejects_escape(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()
    inside = dest / "ok.csv"
    inside.write_text("1", encoding="utf-8")
    assert path_is_inside(dest, inside)
    assert not path_is_inside(dest, tmp_path / "outside.csv")
    assert not path_is_inside(dest, dest.parent)


def test_extract_cannot_escape_session_workspace(tmp_path: Path) -> None:
    from app.package_io import PackageError, extract_package_zip

    dest = package_dir("11" * 16, temp_dir=tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.csv", "a,b\n1,2\n")
        zf.writestr("manifest.json", "{}")
    with pytest.raises(PackageError, match="traversal|Absolute|rejected|inside"):
        extract_package_zip(buf.getvalue(), dest=dest)
    assert not (tmp_path / "evil.csv").exists()
    assert not (workspace_parent(temp_dir=tmp_path) / "evil.csv").exists()


def test_extract_stays_under_dest_after_resolve(tmp_path: Path) -> None:
    from app.package_io import extract_package_zip, wipe_workdir

    dest = package_dir("22" * 16, temp_dir=tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "B",
                    "grid_minutes": 5,
                }
            ),
        )
        zf.writestr("AHU_1/history_wide.csv", "timestamp_utc,fan_status\n2024-01-01T00:00:00Z,1\n")
        zf.writestr("AHU_1/history_wide.json", '{"id":"AHU_1","points":{"fan_status":"fan_status"}}')
    work = extract_package_zip(buf.getvalue(), dest=dest)
    try:
        written = [p for p in work.rglob("*") if p.is_file()]
        assert written
        for p in written:
            assert path_is_inside(dest, p)
    finally:
        wipe_workdir(work)


def test_path_keyed_loads_do_not_share_session_frames(tmp_path: Path) -> None:
    from app.data_loader import load_building_folder

    def _building(root: Path, building_id: str, value: str) -> Path:
        b = root / building_id / "AHU_1"
        b.mkdir(parents=True)
        (b / "history_wide.csv").write_text(
            f"timestamp_utc,fan_status\n2024-01-01T00:00:00Z,{value}\n",
            encoding="utf-8",
        )
        return root / building_id

    a = _building(package_dir("33" * 16, temp_dir=tmp_path), "BLDG_A", "1")
    b = _building(package_dir("44" * 16, temp_dir=tmp_path), "BLDG_B", "9")
    frames_a = load_building_folder(a)
    frames_b = load_building_folder(b)
    assert frames_a["AHU_1"]["fan_status"].iloc[0] == 1
    assert frames_b["AHU_1"]["fan_status"].iloc[0] == 9


def test_exports_dir_is_per_session(tmp_path: Path) -> None:
    a = exports_dir("55" * 16, temp_dir=tmp_path)
    b = exports_dir("66" * 16, temp_dir=tmp_path)
    assert a != b
    (a / "report.docx").write_bytes(b"A")
    assert not (b / "report.docx").exists()
