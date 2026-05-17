#!/usr/bin/env python3
"""BACpypes3 read-only point scrape for discovered remote devices.

The discovery worker already writes `memory/integrations/bacnet_discovery_latest.json`.
This companion script consumes that file, targets the discovered device
addresses/instances directly, and writes a structured JSON report with point
scrape successes or failures. It never writes to field devices.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POINT_LIKE_TYPES = {
    "analog-input",
    "analog-output",
    "analog-value",
    "binary-input",
    "binary-output",
    "binary-value",
    "multi-state-input",
    "multi-state-output",
    "multi-state-value",
}


def build_spec_root() -> Path:
    override = os.environ.get("BAS_BUILD_SPEC_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "py-bacnet-stacks-playground" / "vibe_code_apps_11" / "bas_build_spec"


def discovery_path() -> Path:
    override = os.environ.get("BAS_BACNET_DISCOVERY_JSON", "").strip()
    if override:
        return Path(override).expanduser()
    return build_spec_root() / "memory/integrations/bacnet_discovery_latest.json"


def report_path() -> Path:
    override = os.environ.get("BAS_BACNET_POINT_SCRAPE_JSON", "").strip()
    if override:
        return Path(override).expanduser()
    return build_spec_root() / "memory/integrations/bacnet_point_samples_latest.json"


def load_discovered_targets(path: Path | None = None) -> list[dict[str, Any]]:
    target_path = path or discovery_path()
    if not target_path.is_file():
        return []
    try:
        payload = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    devices = payload.get("devices") if isinstance(payload, dict) else None
    if not isinstance(devices, list):
        return []

    targets: list[dict[str, Any]] = []
    for item in devices:
        if not isinstance(item, dict):
            continue
        instance = item.get("instance")
        address = item.get("address")
        if instance is None or not str(address or "").strip():
            continue
        try:
            instance_int = int(instance)
        except (TypeError, ValueError):
            continue
        targets.append({"instance": instance_int, "address": str(address)})
    return targets


def _normalize_object_identifier(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, tuple) and len(value) == 2:
        return f"{value[0]},{value[1]}"
    text = str(value).strip()
    return text.replace("(", "").replace(")", "").replace("'", "").replace(" ", "")


def _is_point_like(object_identifier: str) -> bool:
    normalized = _normalize_object_identifier(object_identifier)
    object_type = normalized.split(",", 1)[0].strip().lower()
    return object_type in POINT_LIKE_TYPES


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return str(value)


def build_report(
    *,
    bind: str,
    discovery_path: str,
    targets: list[dict[str, Any]],
    target_results: list[dict[str, Any]],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    sample_count = sum(len(result.get("samples") or []) for result in target_results)
    success_count = sum(1 for result in target_results if result.get("ok"))
    return {
        "generated_at_utc": generated_at,
        "bind": bind,
        "discovery_path": discovery_path,
        "target_count": len(targets),
        "targets": targets,
        "result_count": len(target_results),
        "ok_count": success_count,
        "failed_count": len(target_results) - success_count,
        "sample_count": sample_count,
        "results": target_results,
    }


def write_report(report: dict[str, Any], output: Path | None = None) -> Path:
    out_path = output or report_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out_path


async def scrape_targets(
    *,
    app: Any,
    targets: list[dict[str, Any]],
    bind: str,
    discovery_file: str,
    limit: int = 3,
) -> dict[str, Any]:
    from bacpypes3.apdu import AbortPDU
    from bacpypes3.pdu import Address
    from bacpypes3.primitivedata import ObjectIdentifier

    async def read_device_snapshot(target: dict[str, Any]) -> dict[str, Any]:
        device_instance = int(target["instance"])
        device_address = str(target["address"])
        address = Address(device_address)
        device_object = ObjectIdentifier(("device", device_instance))
        result: dict[str, Any] = {
            "instance": device_instance,
            "address": device_address,
            "ok": False,
            "object_list": [],
            "samples": [],
        }

        try:
            obj_list = await app.read_property(address, device_object, "object-list")
        except Exception as err:  # BACnet aborts, no-response, timeouts, etc.
            result["error"] = f"{type(err).__name__}: {err}"
            return result

        normalized_objects = [_normalize_object_identifier(obj) for obj in obj_list]
        result["object_list"] = normalized_objects
        result["ok"] = True

        point_objects = [obj for obj in normalized_objects if _is_point_like(obj)]
        for object_identifier in point_objects[:limit]:
            object_id = _normalize_object_identifier(object_identifier)
            try:
                value = await app.read_property(address, ObjectIdentifier(object_id), "present-value")
            except AbortPDU as err:
                result["samples"].append(
                    {
                        "object": object_id,
                        "property": "present-value",
                        "ok": False,
                        "error": f"{type(err).__name__}: {err}",
                    }
                )
            except Exception as err:  # pragma: no cover - live network path
                result["samples"].append(
                    {
                        "object": object_id,
                        "property": "present-value",
                        "ok": False,
                        "error": f"{type(err).__name__}: {err}",
                    }
                )
            else:
                result["samples"].append(
                    {
                        "object": object_id,
                        "property": "present-value",
                        "ok": True,
                        "value": _serialize_value(value),
                    }
                )

        return result

    target_results = [await read_device_snapshot(target) for target in targets]
    return build_report(
        bind=bind,
        discovery_path=discovery_file,
        targets=targets,
        target_results=target_results,
    )


async def main() -> int:
    from bacpypes3.argparse import SimpleArgumentParser
    from bacpypes3.app import Application

    parser = SimpleArgumentParser()
    args = parser.parse_args()
    app = None
    try:
        app = Application.from_args(args)
        targets = load_discovered_targets()
        bind = os.environ.get("BAS_BACNET_BIND_ADDRESS", "").strip() or getattr(args, "address", "") or "unknown"

        if not targets:
            report = build_report(
                bind=bind,
                discovery_path=str(discovery_path()),
                targets=[],
                target_results=[],
            )
        else:
            report = await scrape_targets(
                app=app,
                targets=targets,
                bind=bind,
                discovery_file=str(discovery_path()),
                limit=max(1, int(os.environ.get("BAS_BACNET_POINT_SCRAPE_LIMIT", "3") or "3")),
            )

        out_path = write_report(report)
        print(json.dumps({"out": str(out_path), "target_count": report["target_count"], "sample_count": report["sample_count"]}))
        return 0
    except Exception as err:
        print(f"An error occurred: {type(err).__name__}: {err}")
        return 1
    finally:
        if app:
            app.close()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
