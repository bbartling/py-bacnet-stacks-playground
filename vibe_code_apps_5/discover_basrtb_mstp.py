# discover_basrtb_mstp.py
#
# pip install bacpypes3
#
# Example:
# python discover_basrtb_mstp.py \
#   --address 192.168.204.50/24 \
#   --network 1 \
#   --instance 599999 \
#   --route-aware \
#   --router-ip 192.168.204.200 \
#   --mstp-net 2000

import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.apdu import ErrorRejectAbortNack


async def safe_read(app, device_address, device_identifier, prop_name):
    try:
        return await app.read_property(device_address, device_identifier, prop_name)
    except ErrorRejectAbortNack as err:
        return f"<{err}>"
    except Exception as err:
        return f"<error: {err}>"


async def main():
    parser = SimpleArgumentParser()

    parser.add_argument(
        "--router-ip",
        default="192.168.204.200",
        help="BASRT-B BACnet/IP address",
    )
    parser.add_argument(
        "--mstp-net",
        type=int,
        default=2000,
        help="MS/TP BACnet network number behind the router",
    )
    parser.add_argument(
        "--low-limit",
        type=int,
        default=0,
        help="lowest BACnet device instance to discover",
    )
    parser.add_argument(
        "--high-limit",
        type=int,
        default=4194303,
        help="highest BACnet device instance to discover",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="seconds to wait for I-Am responses; MS/TP can be slow",
    )
    parser.add_argument(
        "--local-too",
        action="store_true",
        help="also do a local BACnet/IP broadcast on the IP side",
    )

    args = parser.parse_args()

    app = Application.from_args(args)

    try:
        discovered = {}

        # This is the important part for your screenshot:
        # MS/TP network 2000 behind BASRT-B at 192.168.204.200
        mstp_broadcast = Address(f"{args.mstp_net}:*@{args.router_ip}")
        #mstp_broadcast = Address(f"{args.mstp_net}:*")

        print(f"Discovering MS/TP devices at: {mstp_broadcast}")
        i_ams = await app.who_is(
            args.low_limit,
            args.high_limit,
            address=mstp_broadcast,
            timeout=args.timeout,
        )

        for i_am in i_ams:
            instance = i_am.iAmDeviceIdentifier[1]
            discovered[instance] = i_am

        # Optional: discover devices on the BACnet/IP side too
        if args.local_too:
            print("Discovering local BACnet/IP devices with local broadcast: *")
            local_i_ams = await app.who_is(
                args.low_limit,
                args.high_limit,
                address=Address("*"),
                timeout=args.timeout,
            )

            for i_am in local_i_ams:
                instance = i_am.iAmDeviceIdentifier[1]
                discovered[instance] = i_am

        if not discovered:
            print("No devices found.")
            return

        print()
        print(f"Found {len(discovered)} device(s)")
        print("-" * 80)

        for instance in sorted(discovered):
            i_am = discovered[instance]

            device_address = i_am.pduSource
            device_identifier = i_am.iAmDeviceIdentifier

            object_name = await safe_read(
                app,
                device_address,
                device_identifier,
                "object-name",
            )

            description = await safe_read(
                app,
                device_address,
                device_identifier,
                "description",
            )

            print(f"Device Instance: {instance}")
            print(f"BACnet Address:  {device_address}")
            print(f"Object ID:       {device_identifier}")
            print(f"Object Name:     {object_name}")
            print(f"Description:     {description}")
            print(f"Vendor ID:       {i_am.vendorID}")
            print(f"Max APDU:        {i_am.maxAPDULengthAccepted}")
            print(f"Segmentation:    {i_am.segmentationSupported}")
            print("-" * 80)

    finally:
        app.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)