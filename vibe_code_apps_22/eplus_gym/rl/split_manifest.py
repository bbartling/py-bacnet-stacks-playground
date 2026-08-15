"""Deterministic train/validation/locked-test split. Synthetic clones stay with source date."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.rl.day_pool import calendar_fold_key


def _month_block(day_id: str) -> str:
    d = date.fromisoformat(calendar_fold_key(day_id)[:10])
    return f"{d.year:04d}-{d.month:02d}"


def build_split_manifest(
    day_ids: Sequence[str],
    *,
    val_months: tuple[str, ...] = ("2026-03",),
    test_months: tuple[str, ...] = ("2026-01",),
) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for did in day_ids:
        groups.setdefault(calendar_fold_key(did), []).append(str(did))
    train: list[str] = []
    val: list[str] = []
    test: list[str] = []
    for key, ids in sorted(groups.items()):
        blk = _month_block(key)
        if blk in test_months:
            test.extend(ids)
        elif blk in val_months:
            val.extend(ids)
        else:
            train.extend(ids)
    body = {
        "schema": "vibe22.split_manifest.v1",
        "train": sorted(train),
        "validation": sorted(val),
        "locked_test": sorted(test),
        "val_months": list(val_months),
        "test_months": list(test_months),
        "n": {"train": len(train), "validation": len(val), "locked_test": len(test)},
    }
    blob = json.dumps(body, sort_keys=True).encode("utf-8")
    body["sha256"] = hashlib.sha256(blob).hexdigest()
    return body


def assert_no_twin_leakage(manifest: dict[str, Any]) -> None:
    folds = {
        "train": set(calendar_fold_key(x) for x in manifest["train"]),
        "validation": set(calendar_fold_key(x) for x in manifest["validation"]),
        "locked_test": set(calendar_fold_key(x) for x in manifest["locked_test"]),
    }
    if folds["train"] & folds["validation"] or folds["train"] & folds["locked_test"] or folds["validation"] & folds["locked_test"]:
        raise ValueError("source/synthetic twins leaked across splits")


def write_split_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    assert_no_twin_leakage(manifest)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
