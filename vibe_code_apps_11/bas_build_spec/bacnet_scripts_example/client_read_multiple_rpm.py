#!/usr/bin/env python3
"""BACpypes3 client: chunked RPM polling loop + CSV log (runs until Ctrl-C).

  python3 bas_build_spec/bacnet_scripts_example/client_read_multiple_rpm.py \
    --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug
"""
import asyncio
import csv
import os
from datetime import datetime, date, timezone

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier, Atomic
from bacpypes3.apdu import PropertyReference, ErrorType
from bacpypes3.constructeddata import AnyAtomic

"""
python bacpypes3_version_2.py --name BensReadApp --instance 100 --address 192.168.204.11/24:47808 --debug

Hard-coded RPM polling + append-to-CSV logging (Excel-friendly) with DAILY ROTATION.
Retrofitted for bacpypes3.

Behavior:
- Writes to:   data_logs/bacnet_rpm_YYYY-MM-DD.csv
- Auto-rotates at local midnight (new file each day)
- Creates file with headers if missing/empty
- Appends one row per poll cycle
"""

SLEEP_TIME_SECONDS = 5

LOG_DIR = "data_logs"
BASE_NAME = "bacnet_rpm"

MY_IP_ADDRESS = "192.168.204.11/24"

VAV_DEVICE_IP = "192.168.204.12"
ZONE_TEMP = "analog-input,1"
VAV_FLOW = "analog-input,2"
ZONE_COOL_STP = "analog-value,1"
ZONE_DEMAND = "analog-value,2"
VAV_FLOW_STP = "analog-value,3"
VAV_DPR_CMD = "analog-output,1"

AHU_DEVICE_IP = "192.168.204.13"
AHU_DAP = "analog-input,1"
AHU_SAT = "analog-input,2"
AHU_MAT = "analog-input,3"
AHU_RAT = "analog-input,4"
AHU_SAFLOW = "analog-input,5"
AHU_OAT = "analog-input,6"
AHU_POWER_MTR = "analog-input,7"
AHU_SF_O = "analog-output,1"
AHU_HTG_VLV = "analog-output,2"
AHU_CLG_VLV = "analog-output,3"
AHU_OA_DPR = "analog-output,4"
AHU_DAP_SP = "analog-value,1"
AHU_SAT_SP = "analog-value,2"
OAT_NETWORKED = "analog-value,3"
AHU_SF_S = "binary-input,1"
AHU_SF_C = "binary-output,1"
AHU_OCC_SCHEDULE = "multi-state-value,1"

VAV_RPM_REQ = {
    "address": VAV_DEVICE_IP,
    "objects": {
        ZONE_TEMP: ["present-value"],
        VAV_FLOW: ["present-value"],
        ZONE_COOL_STP: ["present-value"],
        ZONE_DEMAND: ["present-value"],
        VAV_FLOW_STP: ["present-value"],
        VAV_DPR_CMD: ["present-value"],
    },
}

AHU_RPM_REQ = {
    "address": AHU_DEVICE_IP,
    "objects": {
        AHU_DAP: ["present-value"],
        AHU_SAT: ["present-value"],
        AHU_MAT: ["present-value"],
        AHU_RAT: ["present-value"],
        AHU_SAFLOW: ["present-value"],
        AHU_OAT: ["present-value"],
        AHU_POWER_MTR: ["present-value"],
        AHU_SF_O: ["present-value"],
        AHU_HTG_VLV: ["present-value"],
        AHU_CLG_VLV: ["present-value"],
        AHU_OA_DPR: ["present-value"],
        AHU_DAP_SP: ["present-value"],
        AHU_SAT_SP: ["present-value"],
        OAT_NETWORKED: ["present-value"],
        AHU_SF_S: ["present-value"],
        AHU_SF_C: ["present-value"],
        AHU_OCC_SCHEDULE: ["present-value"],
    },
}

# -----------------------------
# CSV helpers
# -----------------------------
def _excel_timestamp_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _timestamp_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _unwrap_value(property_value):
    """
    Safely extract values from bacpypes3 APDU responses.
    """
    if isinstance(property_value, ErrorType):
        return None  # Or format error: f"Error: {property_value.errorClass}"
    if isinstance(property_value, AnyAtomic):
        property_value = property_value.get_value()
    if hasattr(property_value, "value"):
        return property_value.value
    if isinstance(property_value, (int, float, str, bool, type(None))):
        return property_value
    return str(property_value)

def _short_obj_id(obj_id: str) -> str:
    try:
        obj_type, inst = obj_id.split(",", 1)
        obj_type = obj_type.strip().lower()
        inst = inst.strip()
    except Exception:
        return obj_id.replace("-", "_").replace(",", "_").replace(" ", "")

    type_map = {
        "analog-input": "AI", "analog-output": "AO", "analog-value": "AV",
        "binary-input": "BI", "binary-output": "BO", "binary-value": "BV",
        "multi-state-input": "MSI", "multi-state-output": "MSO", "multi-state-value": "MSV",
    }
    prefix = type_map.get(obj_type, obj_type.upper().replace("-", "_"))
    return f"{prefix}_{inst}"

def _make_cols_from_req(prefix: str, rpm_req: dict):
    objs = (rpm_req or {}).get("objects", {})
    cols = []
    for obj_id in objs.keys():
        cols.append((f"{prefix}.{_short_obj_id(obj_id)}", obj_id))
    return cols

def _make_headers():
    base = ["timestamp_local", "timestamp_utc"]
    vav_cols = _make_cols_from_req("VAV", VAV_RPM_REQ)
    ahu_cols = _make_cols_from_req("AHU", AHU_RPM_REQ)

    headers = base + [name for name, _ in vav_cols] + [name for name, _ in ahu_cols]
    mapping = {name: obj for name, obj in (vav_cols + ahu_cols)}
    return headers, mapping

HEADERS, HEADER_TO_OBJ = _make_headers()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def csv_path_for_day(day: date) -> str:
    return os.path.join(LOG_DIR, f"{BASE_NAME}_{day.isoformat()}.csv")

def ensure_csv_exists(path: str):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()

def append_row(path: str, row: dict):
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

# -----------------------------
# bacpypes3 RPM chunking helper
# -----------------------------
async def readMultiple_chunked(app, device_ip: str, request_dict: dict, chunk_size: int = 25):
    """
    Chunk a bacpypes3 read_property_multiple into smaller batches.
    Returns a flat dict: { "<object_id>": <value>, ... }
    """
    objects = (request_dict or {}).get("objects", {})
    if not objects:
        return {}

    address_obj = Address(device_ip)
    obj_items = list(objects.items())
    merged = {}

    for i in range(0, len(obj_items), chunk_size):
        chunk = obj_items[i : i + chunk_size]
        parameter_list = []

        for obj_id_str, props in chunk:
            obj_id = ObjectIdentifier(obj_id_str)
            parameter_list.append(obj_id)

            prop_ref_list = []
            for prop_str in props:
                prop_ref = PropertyReference(propertyIdentifier=prop_str)
                prop_ref_list.append(prop_ref)
            parameter_list.append(prop_ref_list)

        try:
            response = await app.read_property_multiple(address_obj, parameter_list)
            
            # Map the bacpypes3 tuple response back to a simplified flat dictionary
            for (res_oid, res_pid, res_idx, property_value) in response:
                oid_str = f"{res_oid[0]},{res_oid[1]}"
                
                # Unwrap bacpypes3 specific APDU types (AnyAtomic, ErrorType, etc.)
                val = _unwrap_value(property_value)
                merged[oid_str] = val

        except Exception as e:
            print(f"RPM Chunk failed for {device_ip}: {type(e).__name__}: {e}")

    return merged

# -----------------------------
# Main loop
# -----------------------------
async def main():

    parser = SimpleArgumentParser()
    args, _ = parser.parse_known_args()
    
    if not getattr(args, "address", None):
        args.address = MY_IP_ADDRESS

    app = Application.from_args(args)
    print(f"--- BACpypes3 Application started on {args.address} ---")

    ensure_dir(LOG_DIR)
    current_day = date.today()
    current_csv = csv_path_for_day(current_day)
    ensure_csv_exists(current_csv)

    await asyncio.sleep(1)

    while True:
        today = date.today()
        if today != current_day:
            current_day = today
            current_csv = csv_path_for_day(current_day)
            ensure_csv_exists(current_csv)
            print(f"\n=== Rotated log file: {current_csv} ===")

        try:
            # Gather chunked requests concurrently
            result_vav, result_ahu = await asyncio.gather(
                readMultiple_chunked(app, VAV_DEVICE_IP, VAV_RPM_REQ, chunk_size=25),
                readMultiple_chunked(app, AHU_DEVICE_IP, AHU_RPM_REQ, chunk_size=25),
            )

            row = {h: "" for h in HEADERS}
            row["timestamp_local"] = _excel_timestamp_local()
            row["timestamp_utc"] = _timestamp_utc_iso()

            merged = {}
            merged.update(result_vav or {})
            merged.update(result_ahu or {})

            for col_name, obj_key in HEADER_TO_OBJ.items():
                val = merged.get(obj_key)
                row[col_name] = "" if val is None else val

            for attempt in (1, 2):
                try:
                    ensure_csv_exists(current_csv)
                    append_row(current_csv, row)
                    break
                except FileNotFoundError:
                    if attempt == 2:
                        raise

            print(f"Logged row -> {current_csv} @ {row['timestamp_local']}")

        except Exception as e:
            print(f"\nRPM/logging error: {type(e).__name__}: {e}")

        await asyncio.sleep(SLEEP_TIME_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLogging stopped by user.")
