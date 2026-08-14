"""Optimization study helpers (CLI-first; Streamlit UI archived)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCREENING = "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY"


def _opt_root(site: Path) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "optimization"


def list_studies(site: Path) -> list[Path]:
    root = _opt_root(site)
    if not root.is_dir():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)


def load_study_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except Exception:  # noqa: BLE001
        return None


def approve_recommendation(study_root: Path) -> Path:
    """Write approved_recommendation.json only — no Site Config / BACnet mutation."""
    root = Path(study_root)
    rec_path = root / "recommendation.json"
    if not rec_path.is_file():
        raise FileNotFoundError(rec_path)
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    approved = {
        **rec,
        "approved": True,
        "approved_note": (
            "Approved proposal artifact only — "
            "Site Config / BACnet / champion / ECM NOT modified."
        ),
        "scientific_claim": SCREENING,
    }
    out = root / "approved_recommendation.json"
    out.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
    return out
