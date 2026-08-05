"""Immutable native-run manifests."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eplus_native import PROXY_FORMULA_VERSION, PROVENANCE_NATIVE


@dataclass
class RunManifest:
    run_id: str
    scenario_id: str
    idf_path: str
    idf_sha256: str
    epw_path: str
    epw_sha256: str
    energyplus_exe: str
    energyplus_version: str
    command: list[str]
    started_utc: str
    ended_utc: str
    runtime_sec: float
    exit_code: int
    output_dir: str
    warning_count: int
    severe_count: int
    fatal_count: int
    heat_cop: float
    cool_cop: float
    proxy_formula_version: str = PROXY_FORMULA_VERSION
    provenance: str = ""
    accepted: bool = False
    reject_reasons: list[str] = field(default_factory=list)
    honesty: str = (
        "Ideal Loads + fixed-COP electrical proxy — not a detailed GSHP/GLHE plant."
    )
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def write(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_accepted(m: RunManifest) -> RunManifest:
    m.accepted = True
    m.provenance = PROVENANCE_NATIVE
    m.reject_reasons = []
    return m
