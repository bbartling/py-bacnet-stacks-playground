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
DEVICE_IP = "192.168.204.13"
DEVICE_INSTANCE = 3456789  # change to the real remote device instance

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