"""Fail-closed active RL model manifest. A nonempty path is not a pass."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eplus_gym.site_pins import sha256_file

MANIFEST_NAME = "active_rl_model_v1.json"
REQUIRED_CONTRACTS = {
    "control_contract_version": "control_contract_v2",
    "observation_contract_version": "observation_contract_v3",
    "reward_contract_version": "reward_v2",
}


class ActiveModelError(ValueError):
    """Champion manifest failed closed."""


def load_active_model(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "contracts" / MANIFEST_NAME
    if not path.is_file():
        raise ActiveModelError("missing contracts/active_rl_model_v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_artifact(app_root: Path, rel: str, *, kind: str) -> dict[str, Any]:
    path = Path(app_root) / str(rel)
    if not path.is_file():
        raise ActiveModelError(f"{kind} artifact missing: {rel}")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ActiveModelError(f"{kind} artifact is not valid JSON: {rel}") from exc
    if not isinstance(body, dict):
        raise ActiveModelError(f"{kind} artifact is not an object: {rel}")
    return body


def _require_pass(body: dict[str, Any], *, kind: str) -> None:
    if body.get("passed") is True:
        return
    if str(body.get("status") or "").lower() in {"pass", "passed", "ok"}:
        return
    raise ActiveModelError(f"{kind} artifact is not a pass (nonempty path is not evidence)")


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
    if str(body.get("energyplus_version") or "") != "26.1.0":
        raise ActiveModelError("energyplus_version must be 26.1.0")
    for key, expected in REQUIRED_CONTRACTS.items():
        if body.get(key) != expected:
            raise ActiveModelError(f"{key} must be {expected}")
    action_v = str(body.get("action_contract_version") or "")
    if action_v not in {"ppo_action_contract_v2", "dqn_action_contract_v2"}:
        raise ActiveModelError("action_contract_version must be ppo or dqn v2")
    if str(body.get("heldout_status") or "") != "locked_unseen":
        raise ActiveModelError("heldout_status must remain locked_unseen")
    for key, kind in (
        ("transient_validation_artifact", "transient/ramp"),
        ("warning_gate_artifact", "W2A"),
        ("monthly_validation_artifact", "monthly"),
    ):
        rel = body.get(key)
        if not rel:
            raise ActiveModelError(f"manifest missing {key}")
        art = _load_artifact(app_root, str(rel), kind=kind)
        _require_pass(art, kind=kind)
        if kind == "W2A":
            w2a = art.get("scored_runtime_w2a")
            if w2a is None:
                phase = (art.get("w2a_low_airflow_by_phase") or {}).get("scored_runtime")
                w2a = phase
            if int(w2a or 1) != 0:
                raise ActiveModelError("W2A scored-runtime bound is not 0")
        if kind == "transient/ramp" and art.get("passed") is not True:
            raise ActiveModelError("transient/ramp artifact passed is not true")
    return body
