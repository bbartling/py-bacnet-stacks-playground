#!/usr/bin/env python3
"""Trim bas_scan device TOMLs to the poll-harness point set.

Reads ``config/drivers/trim_profile.toml``, keeps only whitelisted devices,
and rewrites each device file with just the listed ``[[points]]``.

Examples:
    python scripts/trim_drivers.py
    python scripts/trim_drivers.py --profile config/drivers/trim_profile.toml
    python scripts/trim_drivers.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _format_device_toml(device: dict, points: list[dict], *, comment: str) -> str:
    lines = [f"# {comment}", ""]
    lines.append(f"name = {_quote(str(device['name']))}")
    lines.append(f"enabled = {str(device.get('enabled', True)).lower()}")
    lines.append(f"device_instance = {int(device['device_instance'])}")
    lines.append(f"host = {_quote(str(device['host']))}")
    lines.append(f"port = {int(device.get('port', 47808))}")

    if device.get("mstp_network") is not None:
        lines.append(f"mstp_network = {int(device['mstp_network'])}")
    if device.get("mstp_mac"):
        macs = ", ".join(str(int(m)) for m in device["mstp_mac"])
        lines.append(f"mstp_mac = [{macs}]")

    lines.append(f"interval_secs = {int(device.get('interval_secs', 10))}")
    lines.append(f"offset_secs = {int(device.get('offset_secs', 0))}")
    lines.append(f"critical = {str(device.get('critical', False)).lower()}")
    lines.append("")

    for pt in points:
        lines.append("[[points]]")
        lines.append(f"enabled = {str(pt.get('enabled', True)).lower()}")
        lines.append(f"object_type = {_quote(str(pt['object_type']))}")
        lines.append(f"object_instance = {int(pt['object_instance'])}")
        lines.append(f"point_name = {_quote(str(pt['point_name']))}")
        if pt.get("units"):
            lines.append(f"units = {_quote(str(pt['units']))}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def load_profile(path: Path) -> tuple[dict, list[dict]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    harness = data.get("harness", {})
    devices = data.get("devices", [])
    return harness, devices


def trim_devices(
    devices_dir: Path,
    profile_devices: list[dict],
    *,
    interval_secs: int,
    dry_run: bool = False,
) -> dict[str, int]:
    wanted = {int(d["instance"]): d for d in profile_devices}
    stats = {"kept": 0, "removed_files": 0, "missing_points": 0}

    paths = sorted(devices_dir.glob("*.toml"))
    if not paths:
        raise SystemExit(f"no device TOMLs in {devices_dir} — run bas_scan first")

    seen: set[int] = set()
    for path in paths:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        inst = int(raw["device_instance"])
        if inst not in wanted:
            stats["removed_files"] += 1
            print(f"remove {path.name} (instance {inst} not in trim profile)")
            if not dry_run:
                path.unlink()
            continue

        spec = wanted[inst]
        keep_names = {str(p) for p in spec.get("points", [])}
        all_points = raw.get("points", [])
        kept = [p for p in all_points if str(p.get("point_name", "")) in keep_names]
        found = {str(p.get("point_name", "")) for p in kept}
        missing = sorted(keep_names - found)
        if missing:
            stats["missing_points"] += len(missing)
            print(f"WARN {path.name}: missing points {missing}")

        raw["enabled"] = True
        raw["interval_secs"] = interval_secs
        raw["offset_secs"] = int(spec.get("offset_secs", raw.get("offset_secs", 0)))
        raw["critical"] = bool(spec.get("critical", raw.get("critical", False)))

        comment = (
            f"Device: {raw['name']} (BACnet instance {inst}) — trimmed poll set"
        )
        text = _format_device_toml(raw, kept, comment=comment)
        print(f"trim  {path.name}: {len(kept)} point(s) {sorted(found)}")
        if not dry_run:
            path.write_text(text, encoding="utf-8")
        stats["kept"] += 1
        seen.add(inst)

    for inst, spec in wanted.items():
        if inst not in seen:
            print(f"WARN: profile instance {inst} not found after scan")

    return stats


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        default=root / "config/drivers/trim_profile.toml",
    )
    parser.add_argument(
        "--devices-dir",
        type=Path,
        default=root / "config/drivers/devices",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    harness, profile_devices = load_profile(args.profile.expanduser().resolve())
    interval = int(harness.get("poll_interval_secs", 10))
    stats = trim_devices(
        args.devices_dir.expanduser().resolve(),
        profile_devices,
        interval_secs=interval,
        dry_run=args.dry_run,
    )
    print(
        f"done: kept={stats['kept']} removed={stats['removed_files']} "
        f"missing_points={stats['missing_points']}"
    )
    return 0 if stats["missing_points"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
