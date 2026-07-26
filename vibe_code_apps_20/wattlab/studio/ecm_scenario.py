"""Load / save ``reports/ecm_scenario.json`` for agent ↔ Studio ECMs mirror."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ECM_SCENARIO_NAME = "ecm_scenario.json"
ECM_SCENARIO_VERSION = 4


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
        "sort_preference": "implementation_complexity",
        "package_hints": [],
        "proxy_defaults": {},
        "roi_param_hints": {},
        "notebook_package_id": None,
        "notebook_path": None,
        "input_overrides": {},
        "twin_run": None,
        "updated_at": None,
        "notes": "",
        "recommendations": [],
        "status": "empty — waiting agent or Rebuild from scenario",
    }


def _normalize_status(body: dict[str, Any]) -> None:
    ids = body.get("selected_ecm_ids") or []
    if ids:
        body["status"] = f"{len(ids)} ECMs selected"
        if body.get("notebook_package_id"):
            body["status"] += f" · notebook={body['notebook_package_id']}"
        if body.get("twin_run"):
            body["status"] += " · twin attached"
    else:
        body["status"] = "empty — waiting agent or Rebuild from scenario"


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
    out["sort_preference"] = str(out.get("sort_preference") or "implementation_complexity")
    for key in ("package_hints",):
        value = out.get(key)
        out[key] = [str(item) for item in value] if isinstance(value, list) else []
    for key in ("proxy_defaults", "roi_param_hints", "input_overrides"):
        out[key] = dict(out.get(key) or {}) if isinstance(out.get(key), dict) else {}
    if out.get("notebook_package_id"):
        out["notebook_package_id"] = str(out["notebook_package_id"])
    if out.get("notebook_path"):
        out["notebook_path"] = str(out["notebook_path"])
    if out.get("twin_run"):
        out["twin_run"] = str(out["twin_run"])
    else:
        out["twin_run"] = None
    _normalize_status(out)
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
    body["sort_preference"] = str(body.get("sort_preference") or "implementation_complexity")
    body["package_hints"] = [
        str(item) for item in (body.get("package_hints") or [])
    ] if isinstance(body.get("package_hints"), list) else []
    for key in ("proxy_defaults", "roi_param_hints", "input_overrides"):
        body[key] = dict(body.get(key) or {}) if isinstance(body.get(key), dict) else {}
    if body.get("notebook_package_id"):
        body["notebook_package_id"] = str(body["notebook_package_id"])
    if body.get("notebook_path"):
        body["notebook_path"] = str(body["notebook_path"])
    if body.get("twin_run"):
        body["twin_run"] = str(body["twin_run"])
    else:
        body["twin_run"] = None
    body["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _normalize_status(body)
    p.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return p
