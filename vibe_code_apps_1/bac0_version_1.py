import asyncio
import BAC0

"""
BACnet read on a bacnet.read
<addr> <obj> <inst> <prop> <value>

BACnet write notes on a bacnet._write
<addr> <obj> <inst> <prop> <value> - <priority>
"""

DEVICE_IP = "192.168.204.12"

READ_OBJ_TYPE = "analog-input"
READ_INSTANCE = "1"

WRITE_OBJ_TYPE = "analog-output"
WRITE_INSTANCE = "1"

async def main():
    async with BAC0.start(ping=False) as bacnet:
        await asyncio.sleep(1)

        """ONLY for demo purposes dont execute a WHOIS in production scraping
        It is a global request and can conjest networks
        ONLY conduct WHO-IS less than a once an hour interval"""
        devices = await bacnet.who_is(low_limit=1, high_limit=3456800, timeout=5)

        for d in devices:
            src = str(getattr(d, "pduSource", "")).split(":")[0]
            dev = getattr(d, "iAmDeviceIdentifier", None)  # usually ('device', instance)
            print("Device IP Address: ", src, " - Instance ID: ", dev[1])

        sensor = await bacnet.read(f"{DEVICE_IP} {READ_OBJ_TYPE} {READ_INSTANCE} present-value")
        print("sensor:", sensor)

        before = await bacnet.read(f"{DEVICE_IP} {WRITE_OBJ_TYPE} {WRITE_INSTANCE} present-value")
        print("writing_point before:", before)

        await bacnet._write(f"{DEVICE_IP} {WRITE_OBJ_TYPE} {WRITE_INSTANCE} present-value 88.0 - 10")

        after = await bacnet.read(f"{DEVICE_IP} {WRITE_OBJ_TYPE} {WRITE_INSTANCE} present-value")
        print("writing_point after:", after)

        await bacnet._write(f"{DEVICE_IP} {WRITE_OBJ_TYPE} {WRITE_INSTANCE} present-value null - 10")

        after_release = await bacnet.read(f"{DEVICE_IP} {WRITE_OBJ_TYPE} {WRITE_INSTANCE} present-value")
        print("writing_point after:", after_release)


if __name__ == "__main__":
    asyncio.run(main())
