"""Active-run resolution: latest publish wins unless human pinned."""

from __future__ import annotations

from pathlib import Path

from wattlab.studio.pages.twin_calibrate import resolve_active_run_dir


def _mk_run(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "run_manifest.json").write_text('{"run_id":"%s","status":"ok"}' % name, encoding="utf-8")
    return d


def test_resolve_prefers_current_run_over_stale_session(tmp_path: Path):
    runs = tmp_path / "runs"
    old = _mk_run(runs, "old_run")
    new = _mk_run(runs, "new_run")
    (runs / "CURRENT_RUN.txt").write_text(str(new.resolve()), encoding="utf-8")
    # Stale session without pin → CURRENT_RUN wins
    got = resolve_active_run_dir(runs, session_active=str(old), pinned=False)
    assert got is not None
    assert got.resolve() == new.resolve()


def test_resolve_pin_sticks(tmp_path: Path):
    runs = tmp_path / "runs"
    old = _mk_run(runs, "old_run")
    new = _mk_run(runs, "new_run")
    (runs / "CURRENT_RUN.txt").write_text(str(new.resolve()), encoding="utf-8")
    got = resolve_active_run_dir(runs, session_active=str(old), pinned=True)
    assert got is not None
    assert got.resolve() == old.resolve()


def test_resolve_falls_back_to_newest_mtime(tmp_path: Path):
    runs = tmp_path / "runs"
    _mk_run(runs, "a")
    b = _mk_run(runs, "b")
    # Touch b to be newest
    b.touch()
    got = resolve_active_run_dir(runs, session_active=None, pinned=False)
    assert got is not None
    assert got.name == "b"
