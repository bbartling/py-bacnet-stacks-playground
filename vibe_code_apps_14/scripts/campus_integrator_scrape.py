#!/usr/bin/env python3
"""
Systems integrator scrape — flat campus, one UDP port per building (Reddit / Trane style).

No BACnet router required. Poll each building at IP:port (and optional field-panel port).

  pip install bacpypes3 ifaddr pyyaml
  python campus_integrator_scrape.py
  python campus_integrator_scrape.py --config campus_buildings.yml
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier


def _load_config(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


async def scrape_target(
    app: Application,
    label: str,
    ip: str,
    port: int,
    instance: int,
    read_object: str,
) -> bool:
    dest = Address(f"{ip}:{port}")
    print(f"\n=== {label}  @ {dest}  (instance {instance}) ===")

    iams = await app.who_is(instance, instance, address=dest)
    if not iams:
        print("FAIL  no I-Am — wrong port or device down?", file=sys.stderr)
        return False

    for iam in iams:
        vid = getattr(iam, "vendorID", None)
        print(
            f"OK    I-Am  {iam.iAmDeviceIdentifier}  vendor={vid}  from {iam.pduSource}"
        )

    point = ObjectIdentifier(read_object)
    try:
        value = await app.read_property(dest, point, "present-value")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  ReadProperty {read_object}: {exc}", file=sys.stderr)
        return False

    print(f"OK    {read_object}.present-value = {value!r}")
    return True


async def scrape_building(app: Application, building: Dict[str, Any]) -> bool:
    ok = True
    ip = building["ip"]
    label_base = building.get("label", building["id"])

    for role in ("front", "field"):
        block: Optional[Dict[str, Any]] = building.get(role)
        if not block:
            continue
        port = block.get("port", building["port"])
        inst = block["instance"]
        robj = block.get("read_object", "analog-value,1")
        role_label = f"{label_base} [{role}]"
        ok = await scrape_target(app, role_label, ip, port, inst, robj) and ok

    return ok


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "config" / "campus_buildings.yml",
    )
    parser.add_argument("--client-bind", default="0.0.0.0:47813")
    args = parser.parse_args()

    cfg = _load_config(args.config)
    buildings: List[Dict[str, Any]] = cfg.get("buildings", [])

    print("Flat campus integrator scrape (unique UDP port per building)")
    print(f"LAN: {cfg.get('campus_lan', '?')}")
    print(f"Buildings in config: {len(buildings)}")
    print(f"Client bind: {args.client_bind}")

    bp = SimpleArgumentParser()
    app = Application.from_args(bp.parse_args(["--address", args.client_bind]))

    ok = True
    for bldg in buildings:
        ok = await scrape_building(app, bldg) and ok

    app.close()
    if ok:
        print("\nPASS  integrator scrape completed")
        return 0
    print("\nFAIL  one or more buildings failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
