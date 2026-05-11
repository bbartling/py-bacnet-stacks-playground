Runnable copies for humans and Codex live under **`bas_build_spec/bacnet_scripts_example/`** (see that folder’s `README.md`). This file keeps the full embedded reference corpus.

Example scripts:
- bacnet client read write release null → `bacnet_scripts_example/client_read_write_release.py`
- bacnet client read multiple → `bacnet_scripts_example/client_read_multiple_rpm.py`
- bacnet client priority array → `bacnet_scripts_example/client_priority_array.py`
- bacnet server for schedule object → `bacnet_scripts_example/server_schedule_calendar.py`
- bacnet server example (weather gateway) → `bacnet_scripts_example/server_weather_gateway.py`
- bacnet client points discovery → `bacnet_scripts_example/point_discovery.py` (Who-Is sweep) and `client_device_object_list.py` (known device)

**Human gate:** validate `SimpleArgumentParser` args with `point_discovery.py` before AI copies bind/name/instance into `bas_app` drivers. **Server/gateway** code must stay **long-running** (`while True` / `await asyncio.Future()`), not per-request start/stop.

import asyncio
import sys
import logging

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier, Null

# Configuration
DEVICE_IP = "192.168.204.12"
READ_POINT = "analog-input,1"
WRITE_POINT = "analog-output,1"

"""
Run example:

python .\bacpypes3_version.py --name BensReadApp --instance 100 --address 192.168.204.11/24:47808 --debug
"""

async def main():

    logging.getLogger("__main__")

    parser = SimpleArgumentParser()
    args = parser.parse_args()
    app = Application.from_args(args)

    try:
        print("--- Starting Discovery ---")
        i_ams = await app.who_is(1, 3456800)
        for i_am in i_ams:
            print(f"Device Instance: {i_am.iAmDeviceIdentifier[1]} | Address: {i_am.pduSource}")

        target_address = Address(DEVICE_IP)

        # Reading Property
        sensor_val = await app.read_property(
            target_address,
            ObjectIdentifier(READ_POINT),
            "present-value"
        )
        print(f"Sensor ({READ_POINT}): {sensor_val}")

        # Writing 88.0 at Priority 10
        print(f"Writing 88.0 to {WRITE_POINT} at priority 10...")
        await app.write_property(
            target_address,
            ObjectIdentifier(WRITE_POINT),
            "present-value",
            88.0,
            priority=10
        )

        # Confirm write
        after = await app.read_property(
            target_address,
            ObjectIdentifier(WRITE_POINT),
            "present-value"
        )
        print(f"Value after write: {after}")

        # Release (Write Null) at Priority 10
        print(f"Releasing priority 10 on {WRITE_POINT}...")
        await app.write_property(
            target_address,
            ObjectIdentifier(WRITE_POINT),
            "present-value",
            Null(()),
            priority=10
        )

        # Final check
        after_release = await app.read_property(
            target_address,
            ObjectIdentifier(WRITE_POINT),
            "present-value"
        )
        print(f"Value after release: {after_release}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)



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



import asyncio
import sys
import logging

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier

# Configuration
DEVICE_IP = "192.168.204.13"
TARGET_POINT = "analog-value,3"  # Commandable point

"""
Run example:


python read_priority_array.py --address 192.168.204.11/24:47808 --debug

"""

async def main():

    logging.getLogger("__main__")

    parser = SimpleArgumentParser()
    args = parser.parse_args()
    app = Application.from_args(args)

    try:
        target_address = Address(DEVICE_IP)
        target_obj = ObjectIdentifier(TARGET_POINT)

        print(f"--- Reading Priority Array for {TARGET_POINT} at {DEVICE_IP} ---")

        # Reading the priority-array property
        response = await app.read_property(
            target_address,
            target_obj,
            "priority-array"
        )

        if not response:
            print(f"No priority-array returned for {TARGET_POINT}")
            return

        print("\n--- Priority Array Results ---")

        print(type(response), response)
        
        # Parsing logic referenced from client_utils.py
        parsed_priority_array = []
        for index, priority_value in enumerate(response):
            # BACpypes3 priority values use a _choice attribute to denote the type (e.g., 'null', 'real')
            value_type = priority_value._choice
            value = getattr(priority_value, value_type, None)

            parsed_priority_array.append(
                {
                    "priority_level": index + 1,
                    "type": value_type,
                    "value": value if value is not None else None,
                }
            )
            
            # Print each slot clearly
            print(f"Priority {index + 1:02d}: type={value_type}, value={value}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


#!/usr/bin/env python3
"""
Mini Schedule + Calendar BACnet Device (BACpypes3)
=================================================

A minimal BACnet/IP server device for testing BACnet Schedule + Calendar objects
using BACpypes3.

What this device exposes
------------------------
1) Calendar Object:  calendar,1
   - Name: "Holiday-Calendar"
   - dateList: includes a single holiday date (Dec 25, 2025)
   - Purpose: used by the Schedule object's exceptionSchedule

2) Schedule Object:  schedule,1
   - Name: "Office-Hours-Schedule"
   - weeklySchedule: Mon–Fri 08:00 → 1, 17:00 → 0; Sat/Sun 00:00 → 0
   - exceptionSchedule: references calendar,1 (holiday), forces value 0 on holidays
   - presentValue: maintained by the BACnet Schedule object logic

3) Binary Value Object: binaryValue,1
   - Name: "occupied-bv"
   - Mirrors the Schedule presentValue (active when presentValue is non-zero)

Typical testing workflow
------------------------
- Read device objectName / objectList from the device.
- Read schedule,1 presentValue
- Read schedule,1 weeklySchedule
- Read calendar,1 dateList
- Observe occupied-bv track the schedule presentValue.

Usage
-----
    python mini-schedule-calendar-device.py --name BensScheduleServer --instance 123456 --debug

Arguments
---------
--name       BACnet device name (e.g., "BensScheduleServer")
--instance   BACnet device instance ID (e.g., 123456)
--address    Optional override for IP/port binding (BACpypes3 address string)
--debug      Enable verbose debug logging
"""

import asyncio
import sys
from datetime import datetime, time
from typing import Optional

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger

# Local objects
from bacpypes3.local.binary import BinaryValueObject
from bacpypes3.local.schedule import ScheduleObject
from bacpypes3.local.object import Object as LocalObject

# Standard BACnet objects / types
from bacpypes3.object import CalendarObject
from bacpypes3.basetypes import (
    DailySchedule,
    TimeValue,
    DateRange,
    CalendarEntry,
    SpecialEvent,
    SpecialEventPeriod,
)
from bacpypes3.primitivedata import Integer, Unsigned, Time, Date, ObjectIdentifier


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_debug = 0
_log = ModuleLogger(globals())


# ---------------------------------------------------------------------------
# Human-readable constants (make the schedule definition obvious)
# ---------------------------------------------------------------------------

# BACnet schedule ordering is 7 entries: Monday .. Sunday
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6

WEEKDAYS = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
WEEKENDS = [SATURDAY, SUNDAY]

# Office hours
OFFICE_OPEN = time(8, 0)
OFFICE_CLOSE = time(17, 0)
START_OF_DAY = time(0, 0)

# Occupancy semantics (kept as Integer 0/1 since your JSON output is working)
OCCUPIED = Integer(1)
UNOCCUPIED = Integer(0)


# ---------------------------------------------------------------------------
# Custom Class: LocalCalendarObject
# ---------------------------------------------------------------------------

class LocalCalendarObject(CalendarObject, LocalObject):
    """
    A CalendarObject that can be added to a BACpypes3 Application as a local object.
    """
    notificationClass: Optional[Unsigned] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bacnet_date_tuple(year: int, month: int, day: int) -> tuple[int, int, int, int]:
    """
    Convert a normal date (YYYY, M, D) into the BACnet Date tuple format:
        (year_since_1900, month, day, day_of_week)

    BACnet day_of_week uses 1=Monday ... 7=Sunday.
    """
    dt = datetime(year, month, day)
    bacnet_dow = dt.weekday() + 1  # Monday=1 ... Sunday=7
    return (year - 1900, month, day, bacnet_dow)


def tv(t: time, value: Integer) -> TimeValue:
    """
    Build a TimeValue from a Python time() and a BACnet atomic value.
    """
    return TimeValue(time=Time((t.hour, t.minute, t.second, 0)), value=value)


def build_daily_schedule(entries: list[tuple[time, Integer]]) -> DailySchedule:
    """
    Build a DailySchedule from a list of (time, value) pairs.
    """
    return DailySchedule(daySchedule=[tv(t, v) for t, v in entries])


def build_weekly_schedule() -> list[DailySchedule]:
    """
    Build a 7-day BACnet weekly schedule (Mon..Sun).

    Weekdays:
        08:00 -> 1 (occupied)
        17:00 -> 0 (unoccupied)

    Weekends:
        00:00 -> 0 (unoccupied)
    """
    weekday = build_daily_schedule([
        (OFFICE_OPEN, OCCUPIED),
        (OFFICE_CLOSE, UNOCCUPIED),
    ])

    weekend = build_daily_schedule([
        (START_OF_DAY, UNOCCUPIED),
    ])

    schedule: list[DailySchedule] = [weekend] * 7
    for d in WEEKDAYS:
        schedule[d] = weekday

    return schedule


# ---------------------------------------------------------------------------
# BACnet application
# ---------------------------------------------------------------------------

@bacpypes_debugging
class ScheduleCalendarApplication:
    def __init__(self, args):
        if _debug:
            _log.debug("Initializing ScheduleCalendarApplication")

        self.app = Application.from_args(args)

        # 1) Calendar object (holiday list)
        holiday_date = Date(bacnet_date_tuple(2025, 12, 25))

        self.holiday_calendar = LocalCalendarObject(
            objectIdentifier=("calendar", 1),
            objectName="Holiday-Calendar",
            description="Global Holiday List (used for Schedule exceptions)",
            dateList=[CalendarEntry(date=holiday_date)],
        )

        # 2) Exception schedule: on holiday calendar -> force value 0 all day
        exception_period = SpecialEventPeriod(
            calendarReference=ObjectIdentifier(("calendar", 1))
        )

        special_event = SpecialEvent(
            period=exception_period,
            listOfTimeValues=[tv(START_OF_DAY, UNOCCUPIED)],
            eventPriority=1,
        )

        # 3) Schedule object
        self.schedule_obj = ScheduleObject(
            objectIdentifier=("schedule", 1),
            objectName="Office-Hours-Schedule",
            description="M-F 8-5; weekend closed; holidays closed via Calendar(1)",
            presentValue=Integer(0),
            effectivePeriod=DateRange(
                startDate=Date(bacnet_date_tuple(2024, 1, 1)),
                endDate=Date(bacnet_date_tuple(2030, 12, 31)),
            ),
            weeklySchedule=build_weekly_schedule(),
            exceptionSchedule=[special_event],
            scheduleDefault=UNOCCUPIED,
        )

        # 4) Mirror BV
        self.occupied_bv = BinaryValueObject(
            objectIdentifier=("binaryValue", 1),
            objectName="occupied-bv",
            presentValue="inactive",
            statusFlags=[0, 0, 0, 0],
            description="Mirrors Schedule(1) presentValue (active when non-zero)",
        )

        for obj in (self.holiday_calendar, self.schedule_obj, self.occupied_bv):
            self.app.add_object(obj)

        _log.info("Objects initialized: Calendar(1), Schedule(1), BV(1)")

        asyncio.create_task(self._log_schedule_loop())
        asyncio.create_task(self._mirror_schedule_to_bv_loop())

    async def _log_schedule_loop(self) -> None:
        while True:
            await asyncio.sleep(30.0)
            try:
                pv = self.schedule_obj.presentValue.get_value()
                if _debug:
                    _log.debug(f"Schedule presentValue: {pv!r}")
            except Exception as e:
                if _debug:
                    _log.debug(f"Schedule log loop error: {e!r}")

    async def _mirror_schedule_to_bv_loop(self) -> None:
        while True:
            await asyncio.sleep(5.0)
            try:
                pv = self.schedule_obj.presentValue.get_value()

                # Treat None/0 as inactive, any non-zero as active
                is_active = bool(pv) if pv is not None else False
                new_bv = "active" if is_active else "inactive"

                if self.occupied_bv.presentValue != new_bv:
                    self.occupied_bv.presentValue = new_bv
                    if _debug:
                        _log.debug(f"Updated occupied-bv to {new_bv}")

            except Exception as e:
                if _debug:
                    _log.debug(f"Mirror loop error: {e!r}")


async def main() -> None:
    global _debug

    parser = SimpleArgumentParser()
    args = parser.parse_args()

    if getattr(args, "debug", False):
        _debug = 1
        _log.set_level("DEBUG")

    ScheduleCalendarApplication(args)
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


#!/usr/bin/env python3
"""
Mini BACnet Weather Device
--------------------------
Fetches OpenWeather data every 15 minutes and updates BACnet points every 5 seconds.

BACnet objects:
- analogValue,1  -> web-weather-drybulb-temp
- analogValue,2  -> web-weather-dewpoint-temp
- analogValue,3  -> web-weather-relative-humidity
- binaryValue,1  -> web-weather-fetch-ok


How to Run:
python mini_weather_device.py --name WebWeatherServer --instance 3456 --debug

"""

import asyncio
import math
import os
import sys

import requests
from dotenv import load_dotenv

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.binary import BinaryValueObject
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger

# -----------------------------------------------------------------------------
# Config / constants
# -----------------------------------------------------------------------------

INTERVAL = 5.0  # keep existing BACnet presentValue update interval
WEATHER_FETCH_INTERVAL = 900.0  # 15 minutes

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = os.getenv("CITY", "Madison,WI,US")
UNITS = os.getenv("UNITS", "imperial")  # imperial / metric / standard

_debug = 0
_log = ModuleLogger(globals())


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def calc_dewpoint(temp_value: float, rh_percent: float, units: str) -> float:
    """
    Calculate dew point from dry bulb temperature and relative humidity.

    Magnus formula is used internally in degC, then converted back if needed.
    """
    if rh_percent <= 0:
        raise ValueError("Relative humidity must be greater than 0")

    # Convert input temp to C
    if units == "imperial":
        temp_c = (temp_value - 32.0) * 5.0 / 9.0
    elif units == "metric":
        temp_c = temp_value
    elif units == "standard":
        temp_c = temp_value - 273.15
    else:
        temp_c = temp_value

    # Magnus approximation
    a = 17.625
    b = 243.04  # degC
    gamma = math.log(rh_percent / 100.0) + (a * temp_c) / (b + temp_c)
    dewpoint_c = (b * gamma) / (a - gamma)

    # Convert back to requested units
    if units == "imperial":
        return (dewpoint_c * 9.0 / 5.0) + 32.0
    elif units == "metric":
        return dewpoint_c
    elif units == "standard":
        return dewpoint_c + 273.15
    return dewpoint_c


def build_weather_url() -> str:
    if not API_KEY:
        raise ValueError("OPENWEATHER_API_KEY environment variable is not set")

    return (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={CITY}&appid={API_KEY}&units={UNITS}"
    )


def fetch_weather() -> dict:
    """
    Fetch current weather from OpenWeather and return normalized values.
    """
    url = build_weather_url()
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    data = response.json()
    main = data["main"]

    drybulb = float(main["temp"])
    rh = float(main["humidity"])
    dewpoint = calc_dewpoint(drybulb, rh, UNITS)

    return {
        "drybulb": drybulb,
        "rh": rh,
        "dewpoint": dewpoint,
        "fetch_ok": True,
        "raw": data,
    }


# -----------------------------------------------------------------------------
# BACnet object classes
# -----------------------------------------------------------------------------

@bacpypes_debugging
class SampleApplication:
    """
    BACnet application exposing four points:

    - analogValue,1: web-weather-drybulb-temp
    - analogValue,2: web-weather-dewpoint-temp
    - analogValue,3: web-weather-relative-humidity
    - binaryValue,1: web-weather-fetch-ok
    """

    def __init__(self, args):
        if _debug:
            _log.debug("Initializing SampleApplication")

        self.app = Application.from_args(args)

        temp_units = {
            "imperial": "degreesFahrenheit",
            "metric": "degreesCelsius",
            "standard": "kelvin",
        }.get(UNITS, "degreesFahrenheit")

        # Weather cache
        self.latest_weather = {
            "drybulb": 0.0,
            "dewpoint": 0.0,
            "rh": 0.0,
            "fetch_ok": False,
        }

        # BACnet read-only weather points
        self.web_weather_temp_av = AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="web-weather-drybulb-temp",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.5,
            units=temp_units,
            description="Outdoor dry bulb temperature from OpenWeather",
        )

        self.web_weather_dewpoint_av = AnalogValueObject(
            objectIdentifier=("analogValue", 2),
            objectName="web-weather-dewpoint-temp",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.5,
            units=temp_units,
            description="Outdoor dew point calculated from dry bulb and RH",
        )

        self.web_weather_rh_av = AnalogValueObject(
            objectIdentifier=("analogValue", 3),
            objectName="web-weather-relative-humidity",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="percentRelativeHumidity",
            description="Outdoor relative humidity from OpenWeather",
        )

        self.web_weather_fetch_ok_bv = BinaryValueObject(
            objectIdentifier=("binaryValue", 1),
            objectName="web-weather-fetch-ok",
            presentValue="inactive",
            statusFlags=[0, 0, 0, 0],
            description="Active when latest web weather fetch succeeded",
        )

        for obj in [
            self.web_weather_temp_av,
            self.web_weather_dewpoint_av,
            self.web_weather_rh_av,
            self.web_weather_fetch_ok_bv,
        ]:
            self.app.add_object(obj)

        _log.info("BACnet weather objects initialized.")

        # Start loops
        asyncio.create_task(self.weather_fetch_loop())
        asyncio.create_task(self.update_values())

    async def weather_fetch_loop(self) -> None:
        """
        Fetch weather every 15 minutes and store in cache.
        """
        while True:
            try:
                weather = await asyncio.to_thread(fetch_weather)

                self.latest_weather["drybulb"] = weather["drybulb"]
                self.latest_weather["dewpoint"] = weather["dewpoint"]
                self.latest_weather["rh"] = weather["rh"]
                self.latest_weather["fetch_ok"] = True

                _log.info(
                    "Weather fetch OK | drybulb=%.2f dewpoint=%.2f rh=%.2f",
                    self.latest_weather["drybulb"],
                    self.latest_weather["dewpoint"],
                    self.latest_weather["rh"],
                )

                if _debug:
                    _log.debug(f"Raw weather payload: {weather['raw']}")

            except Exception as err:
                self.latest_weather["fetch_ok"] = False
                _log.error(f"Weather fetch failed: {err}")

            await asyncio.sleep(WEATHER_FETCH_INTERVAL)

    async def update_values(self) -> None:
        """
        Keep existing 5-second BACnet presentValue update loop,
        but now publish the latest cached weather values into BACnet objects.
        """
        while True:
            await asyncio.sleep(INTERVAL)

            self.web_weather_temp_av.presentValue = float(self.latest_weather["drybulb"])
            self.web_weather_dewpoint_av.presentValue = float(self.latest_weather["dewpoint"])
            self.web_weather_rh_av.presentValue = float(self.latest_weather["rh"])
            self.web_weather_fetch_ok_bv.presentValue = (
                "active" if self.latest_weather["fetch_ok"] else "inactive"
            )

            if _debug:
                _log.debug(
                    "BACnet updated | temp=%.2f dewpoint=%.2f rh=%.2f fetch_ok=%s",
                    self.web_weather_temp_av.presentValue,
                    self.web_weather_dewpoint_av.presentValue,
                    self.web_weather_rh_av.presentValue,
                    self.web_weather_fetch_ok_bv.presentValue,
                )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

async def main() -> None:
    global _debug

    parser = SimpleArgumentParser()
    args = parser.parse_args()

    if args.debug:
        _debug = 1
        _log.set_level("DEBUG")
        _log.debug("Debug mode enabled")

    if _debug:
        _log.debug(f"Parsed arguments: {args}")

    SampleApplication(args)

    # run forever
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("Keyboard interrupt received, shutting down.")
        sys.exit(0)


import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.debugging import ModuleLogger

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# Configuration
DEVICE_IP = "192.168.204.18"
DEVICE_INSTANCE = 123456  # change to the real remote device instance

"""
Run example:

python .\bacpypes3_point_discover.py --name BensReadApp --instance 100 --address 192.168.204.11/24:47808 --debug
"""


async def main():
    app = None
    try:
        parser = SimpleArgumentParser()
        args = parser.parse_args()

        if _debug:
            _log.debug("args: %r", args)

        app = Application.from_args(args)

        target_address = Address(DEVICE_IP)
        device_object = ObjectIdentifier(("device", DEVICE_INSTANCE))

        obj_list = await app.read_property(
            target_address,
            device_object,
            "object-list",
        )

        print("OBJECT LIST:", obj_list)
        for obj in obj_list:
            print(obj)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        if app:
            app.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)