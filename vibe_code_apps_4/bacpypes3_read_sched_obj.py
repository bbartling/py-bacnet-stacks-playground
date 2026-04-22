import asyncio
import sys
import logging

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier

# Configuration
DEVICE_IP = "192.168.204.18:47808"
READ_POINT = "schedule,1"

"""
Run example:
python .\bacpypes3_read_sched_obj.py --name BensReadApp --instance 100 --address 192.168.204.11/24:47808 --debug
"""

async def main():
    logging.getLogger("__main__")

    parser = SimpleArgumentParser()
    args = parser.parse_args()
    app = Application.from_args(args)

    try:
        # 1) WHO-IS discovery (global)
        print("\n--- WHO-IS Discovery ---")
        i_ams = await app.who_is()
        if not i_ams:
            print("No I-Am responses received.")
        else:
            for i_am in i_ams:
                print(
                    f"Device Instance: {i_am.iAmDeviceIdentifier[1]} | "
                    f"Address: {i_am.pduSource}"
                )

        # 2) Targeted schedule read
        target_address = Address(DEVICE_IP)
        target_object = ObjectIdentifier(READ_POINT)

        object_name = await app.read_property(target_address, target_object, "object-name")
        present_value = await app.read_property(target_address, target_object, "present-value")
        schedule_default = await app.read_property(target_address, target_object, "schedule-default")
        weekly_schedule = await app.read_property(target_address, target_object, "weekly-schedule")

        # Optional on some minimal schedule implementations
        try:
            exception_schedule = await app.read_property(
                target_address, target_object, "exception-schedule"
            )
        except Exception as exc:
            print(f"exception-schedule not supported: {exc}")
            exception_schedule = []

        if hasattr(present_value, "get_value"):
            present_value = present_value.get_value()
        if hasattr(schedule_default, "get_value"):
            schedule_default = schedule_default.get_value()

        print("\n" + "=" * 60)
        print("BACNET SCHEDULE REPORT")
        print("=" * 60)
        print(f"Schedule Name     : {object_name}")
        print(f"Current Value     : {present_value}")
        print(f"Default Value     : {schedule_default}")

        day_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        print("\nWEEKLY SCHEDULE")
        print("-" * 60)
        for day_index, day in enumerate(weekly_schedule):
            print(f"{day_names[day_index]}:")
            if hasattr(day, "daySchedule") and len(day.daySchedule) > 0:
                for entry in day.daySchedule:
                    entry_time = getattr(entry, "time", None)
                    entry_value = getattr(entry, "value", None)
                    if hasattr(entry_value, "get_value"):
                        entry_value = entry_value.get_value()
                    print(f"  {entry_time} -> {entry_value}")
            else:
                print("  No entries")

        print("\nEXCEPTION SCHEDULE")
        print("-" * 60)
        if len(exception_schedule) == 0:
            print("No exception schedule entries")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)