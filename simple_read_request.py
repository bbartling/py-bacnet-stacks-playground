



"""
192.168.204.12

3456790
analog-input,1
"""

import asyncio
import BAC0

address = "192.168.204.12"
obj_type = "analog-input"
point_addr = "1"

HIGH_ALARM = 80.0
WARNING = 75.0


async def main():
    async with BAC0.start(ping=False) as bacnet:

        reqs = [
            f"{address} {obj_type} {point_addr} present-value",
            f"{address} {obj_type} {point_addr} description",
            f"{address} {obj_type} {point_addr} units",
        ]

        sensor, desc, units = await asyncio.gather(
            *[bacnet.read(r) for r in reqs]
        )

    # -------------------------
    # Boolean + comparison logic
    # -------------------------

    # Truthiness check (None, 0, '', etc.)
    if sensor is None:
        print("Sensor returned no value")
        return

    # Type safety
    if not isinstance(sensor, (int, float)):
        print("Non-numeric sensor value:", sensor)
        return

    # Chained comparisons
    if sensor >= HIGH_ALARM:
        state = "🔥 HIGH ALARM"
    elif WARNING <= sensor < HIGH_ALARM:
        state = "⚠️ WARNING"
    else:
        state = "✅ NORMAL"

    # Boolean combination example
    sensor_ok = 0 <= sensor <= 200          # reasonable engineering range
    has_desc = bool(desc)                  # truthiness
    has_units = bool(units)

    if sensor_ok and has_desc and has_units:
        print(f"{desc}: {sensor:.2f} {units} → {state}")
    else:
        print("Bad metadata or invalid reading")


if __name__ == "__main__":
    asyncio.run(main())

