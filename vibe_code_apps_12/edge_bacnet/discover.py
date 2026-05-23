"""
BACnet Who-Is discovery → object inventory CSV (read-only commissioning).

  python -m edge_bacnet.discover 3456789 -o points_discovered.csv
  python -m edge_bacnet.discover 1 3456799 -o results.csv --site-id acme --building-id tower-a
"""

from __future__ import annotations

import asyncio
import csv
import sys
from typing import Any

from bacpypes3.apdu import AbortPDU, AbortReason, ErrorRejectAbortNack
from bacpypes3.app import Application
from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.basetypes import PropertyIdentifier
from bacpypes3.debugging import ModuleLogger, bacpypes_debugging
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.vendor import get_vendor_info

from edge_bacnet.config import CSV_FIELDNAMES, normalize_row
from edge_bacnet.point_id import make_point_id

_debug = 0
_log = ModuleLogger(globals())
show_warnings = False


@bacpypes_debugging
async def object_identifiers(
    app: Application, device_address: Address, device_identifier: ObjectIdentifier
) -> list[ObjectIdentifier]:
    try:
        return await app.read_property(device_address, device_identifier, "object-list")
    except AbortPDU as err:
        if err.apduAbortRejectReason not in (
            AbortReason.bufferOverflow,
            AbortReason.segmentationNotSupported,
        ):
            if show_warnings:
                sys.stderr.write(f"{device_identifier} object-list abort: {err}\n")
            return []
    except ErrorRejectAbortNack as err:
        if show_warnings:
            sys.stderr.write(f"{device_identifier} object-list error/reject: {err}\n")
        return []

    object_list: list[ObjectIdentifier] = []
    try:
        object_list_length = await app.read_property(
            device_address, device_identifier, "object-list", array_index=0
        )
        for i in range(int(object_list_length)):
            oid = await app.read_property(
                device_address,
                device_identifier,
                "object-list",
                array_index=i + 1,
            )
            object_list.append(oid)
    except ErrorRejectAbortNack as err:
        if show_warnings:
            sys.stderr.write(f"{device_identifier} object-list length error: {err}\n")
    return object_list


async def _read_props(
    app: Application,
    address: Address,
    oid: ObjectIdentifier,
    vendor_info,
) -> dict[str, str]:
    row = {
        "object_name": "",
        "description": "",
        "present_value": "",
        "units": "",
    }
    object_class = vendor_info.get_object_class(oid[0]) if vendor_info else None
    if object_class is None:
        return row

    property_list = None
    try:
        property_list = await app.read_property(address, oid, "property-list")
    except ErrorRejectAbortNack:
        pass

    for property_name in ("object-name", "description", "present-value", "units"):
        try:
            pid = PropertyIdentifier(property_name)
            if property_list and pid not in property_list:
                continue
            if object_class.get_property_type(pid) is None:
                continue
            val = await app.read_property(address, oid, pid)
            if property_name == "object-name":
                row["object_name"] = str(val)
            elif property_name == "description":
                row["description"] = str(val)
            elif property_name == "present-value":
                row["present_value"] = str(val)
            elif property_name == "units":
                row["units"] = str(val)
        except ErrorRejectAbortNack:
            continue
    return row


async def run_discover(
    low_limit: int,
    high_limit: int,
    *,
    output_path: str | None = None,
    site_id: str = "site",
    building_id: str = "building",
    app_args=None,
) -> list[dict[str, Any]]:
    parser = SimpleArgumentParser()
    parser.add_argument("limits", type=int, nargs="+", help="device id or range")
    parser.add_argument("-o", "--output", help="CSV output path")
    parser.add_argument("--site-id", default=site_id)
    parser.add_argument("--building-id", default=building_id)
    warnings_parser = parser.add_mutually_exclusive_group(required=False)
    warnings_parser.add_argument("--warnings", dest="warnings", action="store_true")
    warnings_parser.add_argument("--no-warnings", dest="warnings", action="store_false")
    parser.set_defaults(warnings=False)

    if app_args is None:
        app_args = parser.parse_args()
    global show_warnings
    show_warnings = bool(app_args.warnings)

    app = Application.from_args(app_args)
    csv_rows: list[dict[str, Any]] = []
    defaults = {"site_id": app_args.site_id, "building_id": app_args.building_id}

    try:
        sys.stderr.write(f"Discovering devices {low_limit}..{high_limit}...\n")
        i_ams = await app.who_is(low_limit, high_limit)
        if not i_ams:
            sys.stderr.write("No devices found.\n")
            return []

        sys.stderr.write(f"Found {len(i_ams)} device(s).\n")
        for i_am in i_ams:
            device_address: Address = i_am.pduSource
            device_identifier: ObjectIdentifier = i_am.iAmDeviceIdentifier
            vendor_info = get_vendor_info(i_am.vendorID)
            dev_inst = device_identifier[1]
            dev_addr = str(device_address)
            sys.stderr.write(f" -> {device_identifier} @ {dev_addr}\n")

            for oid in await object_identifiers(app, device_address, device_identifier):
                props = await _read_props(app, device_address, oid, vendor_info)
                raw = {
                    "device_instance": str(dev_inst),
                    "device_address": dev_addr,
                    "object_type": oid[0],
                    "object_instance": str(oid[1]),
                    "object_name": props["object_name"],
                    "description": props["description"],
                    "present_value": props["present_value"],
                    "units": props["units"],
                    "site_id": app_args.site_id,
                    "building_id": app_args.building_id,
                    "system_id": "",
                    "brick_class": "",
                    "brick_tag": "",
                    "enabled": "0",
                    "poll_interval_s": "",
                }
                raw["point_id"] = make_point_id(dev_inst, oid[0], oid[1])
                csv_rows.append(normalize_row(raw, defaults))

        out_path = output_path or getattr(app_args, "output", None)
        out_file = open(out_path, "w", newline="", encoding="utf-8") if out_path else sys.stdout
        try:
            writer = csv.DictWriter(out_file, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        finally:
            if out_path:
                out_file.close()
        sys.stderr.write(f"Wrote {len(csv_rows)} rows.\n")
        return csv_rows
    finally:
        app.close()


async def main() -> None:
    parser = SimpleArgumentParser()
    parser.add_argument("limits", type=int, nargs="+")
    parser.add_argument("-o", "--output")
    parser.add_argument("--site-id", default="site")
    parser.add_argument("--building-id", default="building")
    warnings_parser = parser.add_mutually_exclusive_group(required=False)
    warnings_parser.add_argument("--warnings", dest="warnings", action="store_true")
    warnings_parser.add_argument("--no-warnings", dest="warnings", action="store_false")
    parser.set_defaults(warnings=False)
    args = parser.parse_args()

    if len(args.limits) == 1:
        low, high = args.limits[0], args.limits[0]
    elif len(args.limits) == 2:
        low, high = args.limits[0], args.limits[1]
    else:
        sys.stderr.write("Provide one or two device instance limits.\n")
        sys.exit(1)

    await run_discover(
        low,
        high,
        output_path=args.output,
        site_id=args.site_id,
        building_id=args.building_id,
        app_args=args,
    )


if __name__ == "__main__":
    asyncio.run(main())
