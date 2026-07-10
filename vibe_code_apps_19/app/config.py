"""App configuration — BUILDING_100 demo defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIGS = APP_ROOT / "configs"


@dataclass
class AppConfig:
    data_root: Path
    building_id: str
    weather_subdir: str
    role_map_path: Path
    rule_defaults_path: Path
    app_mode: str  # "local" | "cloud"

    @property
    def is_cloud(self) -> bool:
        return self.app_mode == "cloud"

    @classmethod
    def load(cls) -> AppConfig:
        building_yaml = CONFIGS / "building_100.yaml"
        extra = {}
        if building_yaml.is_file():
            extra = yaml.safe_load(building_yaml.read_text(encoding="utf-8")) or {}
        root = os.environ.get("HVAC_DATA_ROOT") or extra.get("data_root", "./data/hvac_systems_CLEANED")
        building = os.environ.get("HVAC_BUILDING") or extra.get("building_id", "BUILDING_100")
        weather = os.environ.get("HVAC_WEATHER_SUBDIR") or extra.get("weather_subdir", "weather")
        mode = (os.environ.get("APP_MODE") or extra.get("app_mode") or "local").strip().lower()
        if mode not in {"local", "cloud"}:
            mode = "local"
        return cls(
            data_root=Path(root).expanduser().resolve() if Path(root).is_absolute() else (APP_ROOT / root).resolve(),
            building_id=building,
            weather_subdir=weather,
            role_map_path=CONFIGS / "role_map.yaml",
            rule_defaults_path=CONFIGS / "rule_defaults.yaml",
            app_mode=mode,
        )
