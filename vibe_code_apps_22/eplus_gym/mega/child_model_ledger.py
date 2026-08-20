"""Phase 3: immutable A04 parent + versioned child IDF ledger."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.mega._json import sha256_obj, sha256_text, stable_json

SCHEMA = "vibe22.mega.child_model_ledger.v1"
A04_IMMUTABLE_LABEL = "A04_IMMUTABLE_PARENT"


@dataclass
class ChildModelEntry:
    child_name: str
    idf_sha256: str
    parent_sha256: str
    patch_ledger: list[dict[str, Any]]
    rationale: str
    registered_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_name": self.child_name,
            "idf_sha256": self.idf_sha256,
            "parent_sha256": self.parent_sha256,
            "parent_hash": self.parent_sha256,
            "patch_ledger": self.patch_ledger,
            "rationale": self.rationale,
            "registered_at_utc": self.registered_at_utc,
        }


@dataclass
class ChildModelLedger:
    parent_idf_name: str
    parent_sha256: str
    children: list[ChildModelEntry] = field(default_factory=list)

    def register(self, entry: ChildModelEntry) -> None:
        if entry.parent_sha256 != self.parent_sha256:
            raise ValueError("child parent_sha256 must match immutable A04 parent")
        for existing in self.children:
            if existing.child_name == entry.child_name:
                raise ValueError(f"duplicate child_name {entry.child_name!r}")
        self.children.append(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "parent": {
                "name": self.parent_idf_name,
                "sha256": self.parent_sha256,
                "immutable_label": A04_IMMUTABLE_LABEL,
            },
            "children": [c.to_dict() for c in self.children],
            "n_children": len(self.children),
        }

    def write(self, path: Path) -> dict[str, Any]:
        body = self.to_dict()
        body["ledger_sha256"] = sha256_obj(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body


def parent_sha256(idf_path: Path) -> str:
    return hashlib.sha256(idf_path.read_bytes()).hexdigest()


def register_child_model(
    ledger: ChildModelLedger,
    *,
    child_name: str,
    child_idf_path: Path,
    patches: Sequence[dict[str, Any]],
    rationale: str,
) -> ChildModelEntry:
    entry = ChildModelEntry(
        child_name=child_name,
        idf_sha256=hashlib.sha256(child_idf_path.read_bytes()).hexdigest(),
        parent_sha256=ledger.parent_sha256,
        patch_ledger=list(patches),
        rationale=rationale,
    )
    ledger.register(entry)
    return entry


def bootstrap_ledger(parent_idf: Path) -> ChildModelLedger:
    return ChildModelLedger(
        parent_idf_name=parent_idf.name,
        parent_sha256=parent_sha256(parent_idf),
    )


def default_a04_ledger(app_root: Path) -> ChildModelLedger:
    parent = app_root / "models" / "eplus" / A04_IDF_NAME
    ledger = bootstrap_ledger(parent)
    # Placeholder child slots for Phase 4 matrix (hashes from parent until patched).
    for name, rationale in (
        ("a04_child_hp67_scaled_v1", "Per-zone capacity/airflow scaled by 67-HP BAS split"),
        ("a04_child_trackb_bank_v1", "Track B capacity-class bank archetype from parent"),
    ):
        register_child_model(
            ledger,
            child_name=name,
            child_idf_path=parent,
            patches=[{"op": "pending", "note": "Phase 4 physics-repair will materialize"}],
            rationale=rationale,
        )
    return ledger
