"""
Enable polling + BRICK tags on per-device commissioning CSVs.

  python -m edge_bacnet.commission_enable \\
    --dir edge_backup/local/acme/vm-bbartling/points_per_device \\
    --devices-csv edge_backup/local/acme/vm-bbartling/devices_discovered.trim.csv \\
    --poll-interval 60
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

from edge_bacnet.config import CSV_FIELDNAMES, normalize_row
from edge_bacnet.point_id import make_point_id, make_series_id

# JCI VMA standard object names (case-insensitive)
JCI_VMA_BY_NAME: dict[str, tuple[str, str]] = {
    "da-t": ("Discharge_Air_Temperature_Sensor", "DA-T"),
    "zn-t": ("Zone_Air_Temperature_Sensor", "ZN-T"),
    "htg-o": ("Heating_Valve_Command", "HTG-O"),
    "dpr-o": ("Damper_Position_Command", "DPR-O"),
    "zn-sp": ("Zone_Air_Temperature_Setpoint", "ZN-SP"),
    "saflow-sp": ("Supply_Air_Flow_Setpoint", "SAFLOW-SP"),
    "effclg-sp": ("Cooling_Temperature_Setpoint", "EFFCLG-SP"),
    "effhtg-sp": ("Heating_Temperature_Setpoint", "EFFHTG-SP"),
    "sa-f": ("Supply_Air_Flow_Sensor", "SA-F"),
    "clg-o": ("Cooling_Command", "CLG-O"),
}

# Trane UC210 / Symbio
TRANE_BY_NAME: dict[str, tuple[str, str]] = {
    "space temperature local": ("Zone_Air_Temperature_Sensor", "ZN-T"),
    "space temperature setpoint local": ("Zone_Air_Temperature_Setpoint", "ZN-SP"),
    "discharge air temperature": ("Discharge_Air_Temperature_Sensor", "DA-T"),
    "air valve drive status": ("Damper_Position_Sensor", "DPR-STAT"),
    "space co2 concentration local": ("CO2_Level_Sensor", "CO2"),
    "active cool setpoint": ("Cooling_Temperature_Setpoint", "CLG-SP"),
    "active heat setpoint": ("Heating_Temperature_Setpoint", "HTG-SP"),
    "air valve drive command": ("Damper_Position_Command", "DPR-CMD"),
    "heating valve command": ("Heating_Valve_Command", "HTG-CMD"),
    "discharge air flow": ("Supply_Air_Flow_Sensor", "SA-F"),
    "air flow setpoint active": ("Supply_Air_Flow_Setpoint", "SAFLOW-SP"),
}

# RTU-01 (UC600) — common Trane rooftop names
RTU_BY_NAME: dict[str, tuple[str, str]] = {
    "supply air temperature local": ("Supply_Air_Temperature_Sensor", "SAT"),
    "outdoor air temperature local": ("Outside_Air_Temperature_Sensor", "OAT"),
    "return air temperature": ("Return_Air_Temperature_Sensor", "RAT"),
    "mixed air temperature local": ("Mixed_Air_Temperature_Sensor", "MAT"),
    "duct static pressure local": ("Supply_Air_Static_Pressure_Sensor", "SAP"),
    "return air humidity local": ("Return_Air_Humidity_Sensor", "RAH"),
    "supply fan speed command": ("Supply_Fan_Speed_Command", "SF-CMD"),
    "return fan speed output command": ("Return_Fan_Speed_Command", "RF-CMD"),
    "outdoor air damper command": ("Outside_Air_Damper_Command", "OAD-CMD"),
    "cooling capacity status": ("Cooling_Command", "CLG-STAT"),
    "outdoor air temperature bas": ("Outside_Air_Temperature_Sensor", "OAT-BAS"),
}

TRACER_BY_PATTERN: list[tuple[re.Pattern[str], tuple[str, str]]] = [
    (re.compile(r"facility outdoor air temperature", re.I), ("Outside_Air_Temperature_Sensor", "OAT")),
    (re.compile(r"facility outdoor air humidity", re.I), ("Outside_Air_Humidity_Sensor", "OAH")),
    (re.compile(r"averageSpaceTemperature", re.I), ("Zone_Air_Temperature_Sensor", "AVG-ZN-T")),
    (re.compile(r"spaceMaxTemperature", re.I), ("Zone_Air_Temperature_Sensor", "MAX-ZN-T")),
    (re.compile(r"spaceMinTemperature", re.I), ("Zone_Air_Temperature_Sensor", "MIN-ZN-T")),
]


def _norm_name(name: str) -> str:
    return (name or "").strip().lower()


def _load_devices_csv(path: Path) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                inst = int(row["device_instance"])
            except (KeyError, ValueError):
                continue
            out[inst] = row
    return out


def system_id_for_device(inst: int, meta: dict[str, str] | None) -> str:
    meta = meta or {}
    model = (meta.get("model_name") or "").upper()
    name = (meta.get("device_name") or "").upper()
    if "VMA" in model or "VMA" in name:
        return f"jci-vav-{inst}"
    if "UC210" in model or "SYMbio" in model.upper() or "VAV" in name:
        return f"trane-vav-{inst}"
    if inst == 1100 or "RTU" in name:
        return "rtu-01"
    if "TRACER" in model or inst == 10000:
        return "tracer-sc"
    if "HOT WATER" in name.upper() or inst == 1002:
        return "hw-plant"
    return f"bacnet-{inst}"


def brick_for_row(
    inst: int,
    system_id: str,
    object_type: str,
    object_instance: str,
    object_name: str,
) -> tuple[str, str]:
    name = _norm_name(object_name)
    ot = object_type.strip().lower()
    oi = str(object_instance).strip()

    if system_id.startswith("jci-vav-"):
        if name in JCI_VMA_BY_NAME:
            return JCI_VMA_BY_NAME[name]
        # fallback by instance
        jci_inst = {
            "1019": ("Discharge_Air_Temperature_Sensor", "DA-T"),
            "1106": ("Zone_Air_Temperature_Sensor", "ZN-T"),
            "2014": ("Heating_Valve_Command", "HTG-O"),
            "2131": ("Damper_Position_Command", "DPR-O"),
            "1103": ("Zone_Air_Temperature_Setpoint", "ZN-SP"),
            "3515": ("Supply_Air_Flow_Sensor", "SA-F"),
            "3615": ("Cooling_Command", "CLG-O"),
            "3472": ("Cooling_Temperature_Setpoint", "EFFCLG-SP"),
            "3473": ("Heating_Temperature_Setpoint", "EFFHTG-SP"),
            "3384": ("Supply_Air_Flow_Setpoint", "SAFLOW-SP"),
        }
        if oi in jci_inst:
            return jci_inst[oi]

    if system_id.startswith("trane-vav-"):
        if name in TRANE_BY_NAME:
            return TRANE_BY_NAME[name]

    if system_id == "rtu-01" and name in RTU_BY_NAME:
        return RTU_BY_NAME[name]

    if system_id == "tracer-sc":
        for pat, pair in TRACER_BY_PATTERN:
            if pat.search(object_name or ""):
                return pair

    # generic BACnet name hints
    if "zone" in name and "temp" in name and "set" not in name:
        return ("Zone_Air_Temperature_Sensor", "ZN-T")
    if "discharge" in name and "temp" in name:
        return ("Discharge_Air_Temperature_Sensor", "DA-T")
    if "supply" in name and "temp" in name:
        return ("Supply_Air_Temperature_Sensor", "SAT")
    if "outdoor" in name and "temp" in name:
        return ("Outside_Air_Temperature_Sensor", "OAT")

    tag = (object_name or f"{ot}-{oi}").replace(" ", "-")[:32]
    return ("Point", tag)


def commission_file(
    path: Path,
    *,
    meta: dict[str, str] | None,
    poll_interval: int,
    site_id: str,
    building_id: str,
) -> int:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or CSV_FIELDNAMES
        for raw in reader:
            if not raw.get("device_instance"):
                continue
            rows.append({k: str(raw.get(k) or "") for k in fieldnames})

    if not rows:
        return 0

    inst = int(rows[0]["device_instance"])
    system_id = system_id_for_device(inst, meta)

    out_rows: list[dict[str, str]] = []
    for raw in rows:
        brick_class, brick_tag = brick_for_row(
            inst,
            system_id,
            raw.get("object_type", ""),
            raw.get("object_instance", ""),
            raw.get("object_name", ""),
        )
        raw["site_id"] = site_id or raw.get("site_id") or "acme"
        raw["building_id"] = building_id or raw.get("building_id") or "vm-bbartling"
        raw["system_id"] = system_id
        raw["brick_class"] = brick_class
        raw["brick_tag"] = brick_tag
        raw["enabled"] = "1"
        raw["poll_interval_s"] = str(poll_interval)
        if not raw.get("point_id"):
            raw["point_id"] = make_point_id(
                raw["device_instance"], raw["object_type"], raw["object_instance"]
            )
        raw["series_id"] = make_series_id(
            raw["site_id"], raw["building_id"], system_id, raw["point_id"]
        )
        out_rows.append(normalize_row(raw))

    fieldnames = list(CSV_FIELDNAMES)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Enable + BRICK-tag per-device point CSVs")
    ap.add_argument("--dir", type=Path, required=True, help="points_per_device directory")
    ap.add_argument("--devices-csv", type=Path, help="devices_discovered.trim.csv for model hints")
    ap.add_argument("--poll-interval", type=int, default=60)
    ap.add_argument("--site-id", default="acme")
    ap.add_argument("--building-id", default="vm-bbartling")
    ap.add_argument("--only-in-devices-csv", action="store_true", help="Skip devices not in trim list")
    args = ap.parse_args()

    devices = _load_devices_csv(args.devices_csv) if args.devices_csv else {}
    n_files = 0
    n_points = 0
    for path in sorted(args.dir.glob("device_*.csv")):
        if path.name.endswith(".full.csv"):
            continue
        try:
            inst = int(path.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        if args.only_in_devices_csv and inst not in devices:
            continue
        meta = devices.get(inst)
        count = commission_file(
            path,
            meta=meta,
            poll_interval=args.poll_interval,
            site_id=args.site_id,
            building_id=args.building_id,
        )
        if count:
            n_files += 1
            n_points += count
            print(f"{path.name}: {count} points → {system_id_for_device(inst, meta)}")

    print(f"Done: {n_points} points across {n_files} devices")


if __name__ == "__main__":
    main()
