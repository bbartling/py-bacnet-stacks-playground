"""
Apply a trimmed points CSV template to other devices (same object_type + instance + name).

  python -m edge_bacnet.apply_points_template \\
    --template edge_backup/local/acme/vm-bbartling/points_per_device/device_8.csv \\
    --source-dir edge_backup/local/acme/vm-bbartling/points_per_device \\
    --devices 9,10,11,13,14,15,16,19,20,21,24,25,27,29,30,31,34,36,37,38,39
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from edge_bacnet.config import CSV_FIELDNAMES, normalize_row
from edge_bacnet.point_id import make_point_id, make_series_id


def _key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        str(row.get("object_type", "")).strip().lower(),
        str(row.get("object_instance", "")).strip(),
        str(row.get("object_name", "")).strip().upper(),
    )


def load_template(path: Path) -> tuple[list[tuple[str, str, str]], dict[tuple[str, str, str], dict[str, str]]]:
    keys: list[tuple[str, str, str]] = []
    meta: dict[tuple[str, str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            k = _key(row)
            keys.append(k)
            meta[k] = {
                "system_id": row.get("system_id", ""),
                "brick_class": row.get("brick_class", ""),
                "brick_tag": row.get("brick_tag", ""),
                "enabled": row.get("enabled", "0"),
                "poll_interval_s": row.get("poll_interval_s", ""),
            }
    return keys, meta


def apply_to_device(
    source_path: Path,
    dest_path: Path,
    template_keys: list[tuple[str, str, str]],
    template_meta: dict[tuple[str, str, str], dict[str, str]],
) -> tuple[int, list[str]]:
    with source_path.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    if not all_rows:
        return 0, ["empty source file"]

    by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in all_rows:
        by_key[_key(row)] = row

    dev_inst = str(all_rows[0].get("device_instance", "")).strip()
    dev_addr = str(all_rows[0].get("device_address", "")).strip()
    site_id = str(all_rows[0].get("site_id", "site")).strip()
    building_id = str(all_rows[0].get("building_id", "building")).strip()

    out_rows: list[dict[str, str]] = []
    missing: list[str] = []
    for k in template_keys:
        src = by_key.get(k)
        if not src:
            missing.append(f"{k[0]},{k[1]},{k[2]}")
            continue
        m = template_meta[k]
        ot, oi = k[0], k[1]
        pid = make_point_id(dev_inst, ot, oi)
        raw = dict(src)
        raw["device_instance"] = dev_inst
        raw["device_address"] = dev_addr
        raw["system_id"] = m["system_id"] or raw.get("system_id", "")
        raw["brick_class"] = m["brick_class"]
        raw["brick_tag"] = m["brick_tag"]
        raw["enabled"] = m["enabled"]
        raw["poll_interval_s"] = m["poll_interval_s"]
        raw["point_id"] = pid
        raw["series_id"] = make_series_id(
            site_id, building_id, raw["system_id"] or "unknown", pid
        )
        out_rows.append(normalize_row(raw))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    return len(out_rows), missing


def main() -> None:
    ap = argparse.ArgumentParser(description="Copy point selection across similar BACnet devices")
    ap.add_argument("--template", required=True, type=Path, help="Trimmed template CSV (e.g. device_8.csv)")
    ap.add_argument("--source-dir", required=True, type=Path, help="Directory with full device_*.csv files")
    ap.add_argument(
        "--devices",
        required=True,
        help="Comma-separated device instances (e.g. 9,10,11)",
    )
    ap.add_argument(
        "--full-suffix",
        default=".full",
        help="Read source from device_NNN.full.csv if present, else device_NNN.csv",
    )
    args = ap.parse_args()

    template_keys, template_meta = load_template(args.template)
    if not template_keys:
        sys.stderr.write(f"No rows in template {args.template}\n")
        sys.exit(1)

    devices = [d.strip() for d in args.devices.split(",") if d.strip()]
    failed = False
    for dev in devices:
        full_path = args.source_dir / f"device_{dev}{args.full_suffix}.csv"
        src_path = full_path if full_path.is_file() else args.source_dir / f"device_{dev}.csv"
        dest_path = args.source_dir / f"device_{dev}.csv"
        if not src_path.is_file():
            sys.stderr.write(f"MISSING {src_path}\n")
            failed = True
            continue
        n, missing = apply_to_device(src_path, dest_path, template_keys, template_meta)
        msg = f"device_{dev}.csv: {n}/{len(template_keys)} points"
        if missing:
            msg += f" (missing: {', '.join(missing)})"
            failed = True
        sys.stderr.write(msg + "\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
