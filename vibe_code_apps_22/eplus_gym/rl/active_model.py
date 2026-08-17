"""Fail-closed active RL model manifest. A missing champion cannot unlock long training."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eplus_gym.site_pins import sha256_file

MANIFEST_NAME = "active_rl_model_v1.json"


class ActiveModelError(ValueError):
    """Champion manifest failed closed."""


def load_active_model(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "contracts" / MANIFEST_NAME
    if not path.is_file():
        raise ActiveModelError("missing contracts/active_rl_model_v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_active_model(app_root: Path, *, site_epw: Path | None = None) -> dict[str, Any]:
    body = load_active_model(app_root)
    if body.get("long_campaign_allowed") is not True:
        raise ActiveModelError(
            body.get("reason") or "long_campaign_allowed is false; long RL remains blocked"
        )
    idf_rel = body.get("idf_path")
    want_idf = body.get("idf_sha256")
    want_epw = body.get("epw_sha256")
    if not idf_rel or not want_idf:
        raise ActiveModelError("champion idf_path/idf_sha256 missing")
    idf = Path(app_root) / str(idf_rel)
    if not idf.is_file():
        raise ActiveModelError(f"champion IDF missing: {idf_rel}")
    got = sha256_file(idf)
    if got != want_idf:
        raise ActiveModelError(f"champion IDF hash mismatch: {got} != {want_idf}")
    if site_epw is not None and want_epw:
        got_epw = sha256_file(Path(site_epw))
        if got_epw != want_epw:
            raise ActiveModelError(f"EPW hash mismatch: {got_epw} != {want_epw}")
    for key in (
        "control_contract_version",
        "observation_contract_version",
        "action_contract_version",
        "reward_contract_version",
        "transient_validation_artifact",
        "warning_gate_artifact",
        "monthly_validation_artifact",
    ):
        if not body.get(key):
            raise ActiveModelError(f"manifest missing {key}")
    return body
