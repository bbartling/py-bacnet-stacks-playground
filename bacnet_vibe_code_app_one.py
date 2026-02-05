import asyncio
import BAC0

address = "192.168.204.12"
obj_type = "analog-input"
point_addr = "1"

HIGH_ALARM = 80.0
WARNING = 75.0


async def main():
    async with BAC0.start(ping=False) as bacnet:

        await asyncio.sleep(1)  # small settle time

        # -------------------------
        # WHO-IS discovery first
        # -------------------------
        print("Starting whois discovery...")

        devices = await bacnet.who_is()

        device_mapping = {}

        for device in devices:
            if isinstance(device, tuple):
                addr, dev_id = device
                device_mapping[dev_id] = addr
                print(f"Detected device {dev_id} with address {addr}")

        print(device_mapping)
        print(f"{len(device_mapping)} devices discovered on network.\n")

        # -------------------------
        # Now your original reads
        # -------------------------
        sensor = await bacnet.read(
            f"{address} {obj_type} {point_addr} present-value"
        )

        desc = await bacnet.read(
            f"{address} {obj_type} {point_addr} description"
        )

        units = await bacnet.read(
            f"{address} {obj_type} {point_addr} units"
        )

    # -------------------------------------------------
    # Boolean / comparison lesson logic (outside BACnet)
    # -------------------------------------------------

    if sensor is None:
        print("Sensor returned no value")
        return

    if not isinstance(sensor, (int, float)):
        print("Non-numeric sensor value:", sensor)
        return

    if sensor >= HIGH_ALARM:
        state = "HIGH ALARM"
    elif WARNING <= sensor < HIGH_ALARM:
        state = "WARNING"
    else:
        state = "NORMAL"

    sensor_ok = 0 <= sensor <= 200
    has_desc = bool(desc)
    has_units = bool(units)

    if sensor_ok and has_desc and has_units:
        print(f"{desc}: {sensor:.2f} {units} → {state}")
    else:
        print("Bad metadata or invalid reading")



if __name__ == "__main__":
    asyncio.run(main())
