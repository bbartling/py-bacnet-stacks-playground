import asyncio
import BAC0

DEVICE_IP = "192.168.204.13"
READ_OBJ_TYPE = "analog-value"
READ_INSTANCE = "3"

async def main():
    async with BAC0.start(ping=False) as bacnet:
        await asyncio.sleep(1)

        pa = await bacnet.read_priority_array(DEVICE_IP, READ_OBJ_TYPE, READ_INSTANCE)
        print(pa)

if __name__ == "__main__":
    asyncio.run(main())