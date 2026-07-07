"""Point catalog from per-box columns.csv (VAV) or AHU columns.csv."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PointRecord:
    column: str
    point_role: str
    point_name: str
    units: str | None = None


@dataclass
class PointCatalog:
    source: Path
    points: tuple[PointRecord, ...]

    def by_role(self, role: str) -> list[PointRecord]:
        return [p for p in self.points if p.point_role == role]

    def column_for_role(self, role: str) -> str | None:
        hits = self.by_role(role)
        return hits[0].column if hits else None


def _read_columns(path: Path) -> PointCatalog:
    df = pd.read_csv(path)
    records: list[PointRecord] = []
    for row in df.itertuples(index=False):
        records.append(
            PointRecord(
                column=str(getattr(row, "column", "")),
                point_role=str(getattr(row, "point_role", "")),
                point_name=str(getattr(row, "point_name", "")),
                units=getattr(row, "units", None) if hasattr(row, "units") else None,
            )
        )
    return PointCatalog(source=path, points=tuple(records))


def load_vav_catalog(data_root: Path, building: str, vav_id: str) -> PointCatalog:
    path = data_root / building / "VAV" / vav_id / "columns.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return _read_columns(path)


def load_ahu_catalog(data_root: Path, building: str, ahu_name: str) -> PointCatalog:
    path = data_root / building / ahu_name / "columns.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return _read_columns(path)
