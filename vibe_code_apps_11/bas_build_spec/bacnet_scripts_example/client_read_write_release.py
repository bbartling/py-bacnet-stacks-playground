#!/usr/bin/env python3
"""BACpypes3 client: read, write at priority, relinquish (Null). Human lab script.

Run (bind = this host NIC on the BACnet segment):

  cd /home/ben
  python3 bas_build_spec/bacnet_scripts_example/client_read_write_release.py \
    --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug

Validate comms with point_discovery.py first. Edit DEVICE_* below or set env overrides.
"""
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
