"""Load / save ``reports/ecm_scenario.json`` for Easy Buttons ↔ agent handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_ECM_SCENARIO_NAME = "ecm_scenario.json"
ECM_SCENARIO_VERSION = 1


def default_ecm_scenario_path(workspace: Path | None = None) -> Path:
    from wattlab.studio.workspace import reports_dir

    if workspace is not None:
        return Path(workspace) / "reports" / DEFAULT_ECM_SCENARIO_NAME
    return reports_dir() / DEFAULT_ECM_SCENARIO_NAME


def empty_ecm_scenario() -> dict[str, Any]:
    return {
        "version": ECM_SCENARIO_VERSION,
        "selected_ecm_ids": [],
        "measure_set": None,
        "notes": "",
        "recommendations": [],
        "status": "empty — waiting agent or Easy Buttons",
    }


def load_ecm_scenario(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else default_ecm_scenario_path()
    if not p.is_file():
        return empty_ecm_scenario()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_ecm_scenario()
    if not isinstance(raw, dict):
        return empty_ecm_scenario()
    out = empty_ecm_scenario()
    out.update(raw)
    out["version"] = ECM_SCENARIO_VERSION
    ids = out.get("selected_ecm_ids") or []
    if not isinstance(ids, list):
        ids = []
    out["selected_ecm_ids"] = [str(x) for x in ids]
    if out["selected_ecm_ids"]:
        out["status"] = f"{len(out['selected_ecm_ids'])} ECMs selected"
    else:
        out["status"] = "empty — waiting agent or Easy Buttons"
    return out


def save_ecm_scenario(
    payload: dict[str, Any],
    *,
    path: Path | str | None = None,
) -> Path:
    p = Path(path) if path is not None else default_ecm_scenario_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = empty_ecm_scenario()
    body.update(payload or {})
    body["version"] = ECM_SCENARIO_VERSION
    ids = body.get("selected_ecm_ids") or []
    body["selected_ecm_ids"] = [str(x) for x in ids] if isinstance(ids, list) else []
    if body["selected_ecm_ids"]:
        body["status"] = f"{len(body['selected_ecm_ids'])} ECMs selected"
    else:
        body["status"] = "empty — waiting agent or Easy Buttons"
    p.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return p
