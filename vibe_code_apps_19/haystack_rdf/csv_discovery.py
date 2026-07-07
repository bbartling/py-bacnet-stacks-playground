"""Discover historian equipment folders (columns.csv + history_wide.csv) recursively."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HistorianBundle:
    """One equipment historian: metadata columns + wide time-series CSV."""

    equipment_id: str
    history_subdir: str
    columns_path: Path
    history_path: Path


def _is_historian_dir(path: Path) -> bool:
    return (path / "columns.csv").is_file() and (path / "history_wide.csv").is_file()


def discover_historian_bundles(
    root: Path,
    *,
    building_dir: Path | None = None,
) -> list[HistorianBundle]:
    """
    Walk *root* recursively for directories containing columns.csv + history_wide.csv.

    *building_dir* (when set) is used to compute history_subdir relative paths for the
    Haystack model (e.g. ``VAV/VAV_101``). When omitted, subdir is relative to *root*.
    """
    if not root.is_dir():
        return []

    base = building_dir or root
    bundles: list[HistorianBundle] = []
    seen_subdirs: set[str] = set()

    for dirpath, dirnames, _filenames in root.walk():
        current = Path(dirpath)
        if not _is_historian_dir(current):
            continue
        try:
            rel = current.relative_to(base)
            history_subdir = "." if rel.parts == () else rel.as_posix()
        except ValueError:
            history_subdir = current.name

        if history_subdir in seen_subdirs:
            dirnames.clear()
            continue
        seen_subdirs.add(history_subdir)

        eq_id = current.name
        bundles.append(
            HistorianBundle(
                equipment_id=eq_id,
                history_subdir=history_subdir,
                columns_path=current / "columns.csv",
                history_path=current / "history_wide.csv",
            )
        )
        dirnames.clear()

    bundles.sort(key=lambda b: b.history_subdir)
    return bundles


def newest_csv_mtime(bundles: list[HistorianBundle]) -> float:
    latest = 0.0
    for bundle in bundles:
        for path in (bundle.columns_path, bundle.history_path):
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                pass
    return latest
