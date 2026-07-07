"""Auto-bootstrap Haystack model when CSV tree changes (metadata only — no wide CSV load)."""

from __future__ import annotations

import logging
from pathlib import Path

from shared.data_config import DataConfig, get_config

from .csv_bootstrap import bootstrap_and_sync, build_model_from_csv
from .csv_discovery import discover_historian_bundles, newest_csv_mtime
from .model_store import ModelStore

_log = logging.getLogger(__name__)


def _bundle_mtime(paths: list[Path]) -> float:
    latest = 0.0
    for path in paths:
        try:
            if path.is_file():
                latest = max(latest, path.stat().st_mtime)
        except OSError:
            pass
    return latest


def csv_tree_mtime(cfg: DataConfig | None = None) -> float:
    cfg = cfg or get_config()
    latest = 0.0
    if cfg.building_dir.is_dir():
        bundles = discover_historian_bundles(cfg.building_dir, building_dir=cfg.building_dir)
        latest = max(latest, newest_csv_mtime(bundles))
        latest = max(
            latest,
            _bundle_mtime(
                [
                    cfg.building_dir / "vav_to_ahu_simple.csv",
                    cfg.building_dir / "manifest.json",
                ]
            ),
        )
    if cfg.weather_dir.is_dir():
        wx_bundles = discover_historian_bundles(cfg.weather_dir)
        latest = max(latest, newest_csv_mtime(wx_bundles))
    return latest


def model_needs_sync(cfg: DataConfig | None = None) -> bool:
    cfg = cfg or get_config()
    store = ModelStore()
    if not store.path.is_file():
        return True
    model = store.load()
    if not model.get("equipment"):
        return True
    try:
        model_mtime = store.path.stat().st_mtime
    except OSError:
        return True
    return csv_tree_mtime(cfg) > model_mtime


def ensure_model_synced(cfg: DataConfig | None = None, *, force: bool = False) -> Path:
    """Bootstrap model.json + TTL from CSV when missing or stale."""
    cfg = cfg or get_config()
    if force or model_needs_sync(cfg):
        reason = "forced" if force else "csv_changed_or_missing_model"
        preview = build_model_from_csv(cfg)
        _log.info(
            "Haystack auto-sync (%s): %d equipment, %d points",
            reason,
            len(preview.get("equipment") or []),
            len(preview.get("points") or []),
        )
        return bootstrap_and_sync(cfg, force=True)
    from .paths import model_ttl_path
    from .ttl_service import TtlService

    ttl_path = model_ttl_path(cfg.building)
    if not ttl_path.is_file():
        return TtlService().sync()
    return ttl_path
