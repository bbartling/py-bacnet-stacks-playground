"""Load building manifest, AHU history, and VAV terminal boxes."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_APP19 = Path(__file__).resolve().parents[2]
if str(_APP19) not in sys.path:
    sys.path.insert(0, str(_APP19))

from shared.data_config import DataConfig, get_config  # noqa: E402

from fdd_model.catalog import PointCatalog, load_ahu_catalog, load_vav_catalog


@dataclass
class VavBox:
    vav_id: str
    catalog: PointCatalog
    history: pd.DataFrame


@dataclass
class BuildingDataset:
    config: DataConfig
    manifest: dict
    vav_boxes: dict[str, VavBox] = field(default_factory=dict)

    @property
    def poll_seconds(self) -> int:
        return self.config.poll_seconds()

    def load_vav(self, vav_id: str) -> VavBox:
        if vav_id in self.vav_boxes:
            return self.vav_boxes[vav_id]
        root = self.config.data_root
        b = self.config.building
        hist_path = root / b / "VAV" / vav_id / "history_wide.csv"
        df = pd.read_csv(hist_path)
        df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        box = VavBox(vav_id=vav_id, catalog=load_vav_catalog(root, b, vav_id), history=df)
        self.vav_boxes[vav_id] = box
        return box

    def list_vav_ids(self) -> list[str]:
        return self.config.list_vav_boxes()


def load_building_dataset(cfg: DataConfig | None = None) -> BuildingDataset:
    cfg = cfg or get_config()
    manifest_path = cfg.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    return BuildingDataset(config=cfg, manifest=manifest)


def load_ahu_history(cfg: DataConfig, ahu_name: str) -> pd.DataFrame:
    path = cfg.building_dir / ahu_name / "history_wide.csv"
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)
