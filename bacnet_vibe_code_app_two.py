import asyncio
import csv
import os
from datetime import datetime, date, timezone

import BAC0

"""
Hard-coded RPM polling + append-to-CSV logging (Excel-friendly) with DAILY ROTATION.

Behavior:
- Writes to:   data_logs/bacnet_rpm_YYYY-MM-DD.csv
- Auto-rotates at local midnight (new file each day)
- Creates file with headers if missing/empty
- Appends one row per poll cycle
"""

SLEEP_TIME_SECONDS = 60

LOG_DIR = "data_logs"  # long-term storage directory
BASE_NAME = "bacnet_rpm"  # file prefix

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


def _safe_value(props):
    if not props:
        return None
    try:
        return props[0][1]
    except Exception:
        return None


def _make_headers():
    base = ["timestamp_local", "timestamp_utc"]

    vav_cols = [
        ("VAV.ZoneTemp", ZONE_TEMP),
        ("VAV.Flow", VAV_FLOW),
        ("VAV.CoolSP", ZONE_COOL_STP),
        ("VAV.Demand", ZONE_DEMAND),
        ("VAV.FlowSP", VAV_FLOW_STP),
        ("VAV.DPR_Cmd", VAV_DPR_CMD),
    ]

    ahu_cols = [
        ("AHU.DAP", AHU_DAP),
        ("AHU.SAT", AHU_SAT),
        ("AHU.MAT", AHU_MAT),
        ("AHU.RAT", AHU_RAT),
        ("AHU.SAFlow", AHU_SAFLOW),
        ("AHU.OAT", AHU_OAT),
        ("AHU.Power", AHU_POWER_MTR),
        ("AHU.SF_Out", AHU_SF_O),
        ("AHU.HtgVlv", AHU_HTG_VLV),
        ("AHU.ClgVlv", AHU_CLG_VLV),
        ("AHU.OA_DPR", AHU_OA_DPR),
        ("AHU.DAP_SP", AHU_DAP_SP),
        ("AHU.SAT_SP", AHU_SAT_SP),
        ("AHU.OAT_Networked", OAT_NETWORKED),
        ("AHU.SF_Status", AHU_SF_S),
        ("AHU.SF_Cmd", AHU_SF_C),
        ("AHU.OccSchedule", AHU_OCC_SCHEDULE),
    ]

    headers = base + [name for name, _ in vav_cols] + [name for name, _ in ahu_cols]
    mapping = {name: obj for name, obj in (vav_cols + ahu_cols)}
    return headers, mapping


HEADERS, HEADER_TO_OBJ = _make_headers()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def csv_path_for_day(day: date) -> str:
    # Daily file name like: data_logs/bacnet_rpm_2026-02-18.csv
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
# Main loop
# -----------------------------
async def main():
    ensure_dir(LOG_DIR)

    current_day = date.today()
    current_csv = csv_path_for_day(current_day)
    ensure_csv_exists(current_csv)

    async with BAC0.start(ip=MY_IP_ADDRESS, ping=False) as bacnet:
        await asyncio.sleep(1)

        while True:
            # Rotate at local midnight (day changed)
            today = date.today()
            if today != current_day:
                current_day = today
                current_csv = csv_path_for_day(current_day)
                ensure_csv_exists(current_csv)
                print(f"\n=== Rotated log file: {current_csv} ===")

            try:
                result_vav, result_ahu = await asyncio.gather(
                    bacnet.readMultiple(VAV_DEVICE_IP, request_dict=VAV_RPM_REQ),
                    bacnet.readMultiple(AHU_DEVICE_IP, request_dict=AHU_RPM_REQ),
                )

                row = {h: "" for h in HEADERS}
                row["timestamp_local"] = _excel_timestamp_local()
                row["timestamp_utc"] = _timestamp_utc_iso()

                merged = {}
                merged.update(result_vav or {})
                merged.update(result_ahu or {})

                for col_name, obj_key in HEADER_TO_OBJ.items():
                    props = merged.get(obj_key)
                    val = _safe_value(props)
                    row[col_name] = "" if val is None else val


                # NEW: robust against deletion mid-write
                for attempt in (1, 2):
                    try:
                        ensure_csv_exists(current_csv)
                        append_row(current_csv, row)
                        break
                    except FileNotFoundError:
                        if attempt == 2:
                            raise

                print(f"\nLogged row -> {current_csv} @ {row['timestamp_local']}")

            except Exception as e:
                # Note: with this structure, if the RPM fails, no row is written for that cycle.
                # If you want "always write a row" with blanks + error columns, say so and I'll patch it.
                print(f"\nRPM/logging error: {type(e).__name__}: {e}")

            await asyncio.sleep(SLEEP_TIME_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
