"""Deterministic train/validation/locked-test split. Synthetic clones stay with source date."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.rl.day_pool import calendar_fold_key

TRAIN_END = date(2025, 12, 14)
VAL_END = date(2025, 12, 31)
TEST_END = date(2026, 1, 31)


def _source_date(day_id: str) -> date:
    return date.fromisoformat(calendar_fold_key(day_id)[:10])


def fold_for_date(d: date) -> str:
    if d <= TRAIN_END:
        return "train"
    if d <= VAL_END:
        return "validation"
    if d <= TEST_END:
        return "locked_test"
    return "post_test_diagnostic"


def build_split_manifest(
    day_ids: Sequence[str],
    *,
    val_months: tuple[str, ...] | None = None,
    test_months: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Forward split. val_months/test_months ignored except for leakage tests that pass them."""
    groups: dict[str, list[str]] = {}
    for did in day_ids:
        groups.setdefault(calendar_fold_key(did), []).append(str(did))
    train: list[str] = []
    val: list[str] = []
    test: list[str] = []
    diagnostic: list[str] = []
    if val_months is not None or test_months is not None:
        # Legacy month-block path used only by leakage unit tests.
        from datetime import date as _date

        def _month_block(day_id: str) -> str:
            d = _date.fromisoformat(calendar_fold_key(day_id)[:10])
            return f"{d.year:04d}-{d.month:02d}"

        vm = set(val_months or ())
        tm = set(test_months or ())
        for key, ids in sorted(groups.items()):
            blk = _month_block(key)
            if blk in tm:
                test.extend(ids)
            elif blk in vm:
                val.extend(ids)
            else:
                train.extend(ids)
    else:
        for key, ids in sorted(groups.items()):
            fold = fold_for_date(_source_date(key))
            if fold == "train":
                train.extend(ids)
            elif fold == "validation":
                val.extend(ids)
            elif fold == "locked_test":
                test.extend(ids)
            else:
                diagnostic.extend(ids)
    body = {
        "schema": "vibe22.split_manifest.v2",
        "train": sorted(train),
        "validation": sorted(val),
        "locked_test": sorted(test),
        "post_test_diagnostic": sorted(diagnostic),
        "train_end": TRAIN_END.isoformat(),
        "validation_end": VAL_END.isoformat(),
        "locked_test_end": TEST_END.isoformat(),
        "n": {
            "train": len(train),
            "validation": len(val),
            "locked_test": len(test),
            "post_test_diagnostic": len(diagnostic),
        },
    }
    blob = json.dumps({k: body[k] for k in body if k != "sha256"}, sort_keys=True).encode("utf-8")
    body["sha256"] = hashlib.sha256(blob).hexdigest()
    return body


def assert_no_twin_leakage(manifest: dict[str, Any]) -> None:
    folds = {
        "train": set(calendar_fold_key(x) for x in manifest.get("train") or []),
        "validation": set(calendar_fold_key(x) for x in manifest.get("validation") or []),
        "locked_test": set(calendar_fold_key(x) for x in manifest.get("locked_test") or []),
        "post_test_diagnostic": set(
            calendar_fold_key(x) for x in manifest.get("post_test_diagnostic") or []
        ),
    }
    names = list(folds)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if folds[a] & folds[b]:
                raise ValueError(f"source/synthetic twins leaked across {a} and {b}")


def write_split_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    assert_no_twin_leakage(manifest)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def persist_train_fold(
    day_ids: Sequence[str],
    dest: Path,
    *,
    day_specs: Sequence[dict[str, Any]] | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Write split_manifest.json and return only the train fold (and matching specs)."""
    manifest = build_split_manifest(day_ids)
    write_split_manifest(Path(dest), manifest)
    train = list(manifest["train"])
    if not train:
        raise ValueError("train fold is empty; refuse training")
    spec_by_day = {str(s.get("day")): dict(s) for s in (day_specs or []) if s.get("day")}
    specs = [spec_by_day[d] for d in train if d in spec_by_day]
    return train, specs, manifest


def assert_train_fold_only(days: Sequence[str]) -> None:
    extra = [d for d in days if fold_for_date(_source_date(str(d))) != "train"]
    if extra:
        raise ValueError(f"train_sb3 received non-train days: {extra[:8]}")
