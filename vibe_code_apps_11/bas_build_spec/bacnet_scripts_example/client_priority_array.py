#!/usr/bin/env python3
"""BACpypes3 client: read priority-array on a commandable point.

  python3 bas_build_spec/bacnet_scripts_example/client_priority_array.py \
    --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug
"""
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
