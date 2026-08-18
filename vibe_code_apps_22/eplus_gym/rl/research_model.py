"""Fail-closed research RL twin. Cannot enable long_campaign_allowed."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_CRLF
from eplus_gym.site_pins import sha256_file

MANIFEST_NAME = "research_rl_model_v1.json"


class ResearchModelError(ValueError):
    """Research PoC contract failed closed."""


def load_research_model(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "contracts" / MANIFEST_NAME
    if not path.is_file():
        raise ResearchModelError("missing contracts/research_rl_model_v1.json")
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ResearchModelError("research contract is not an object")
    return body


def verify_research_model(
    app_root: Path,
    *,
    override: Mapping[str, Any] | None = None,
    site_idf: Path | None = None,
) -> dict[str, Any]:
    body = dict(override) if override is not None else load_research_model(app_root)
    if body.get("long_campaign_allowed") is True:
        raise ResearchModelError("research contract must not set long_campaign_allowed=true")
    if body.get("research_poc_allowed") is not True:
        raise ResearchModelError("research_poc_allowed must be true")
    if body.get("simulation_training_ready") is True:
        raise ResearchModelError("research twin is not SIMULATION_TRAINING_READY")
    if body.get("operational_dsm_ready") is True:
        raise ResearchModelError("OPERATIONAL_DSM_READY must remain false")
    if str(body.get("model_id") or "") in {"champion", "best", "validated", "active"}:
        raise ResearchModelError("research twin must not be labeled champion/validated/active")
    idf_rel = body.get("idf_path") or f"models/eplus/{A04_IDF_NAME}"
    want = str(body.get("idf_sha256") or A04_SHA_CRLF)
    idf = Path(app_root) / str(idf_rel)
    if site_idf is not None:
        idf = Path(site_idf)
    if idf.is_file():
        got = sha256_file(idf)
        if Path(idf).name == A04_IDF_NAME:
            if got not in A04_SHA_ALLOWED:
                raise ResearchModelError(f"research IDF hash mismatch: {got}")
        elif want and got != want:
            raise ResearchModelError(f"research IDF hash mismatch: {got}")
    return body
