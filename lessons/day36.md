# Day 36 – Playing with a Mini BACnet Device

## Goal

Set up a simple BACnet/IP server using the provided `mini-device-revisited.py`
script, explore its objects and write a small algorithm to control a
commandable point based on a sensor reading.  This exercise introduces
rudimentary building automation control and demonstrates how Python can be
used to interface with BACnet devices.

## Concept

The `mini-device-revisited.py` script (included in the course repository)
creates a minimal **BACnet server** using the BACpypes 3 library.  The
device exposes four objects:

* A read‑only **Analog Value** (AV) object that ramps its `presentValue`
  periodically.
* A read‑only **Binary Value** (BV) object that toggles between `active`
  and `inactive`.
* A **commandable AV** object that supports writes via the BACnet priority
  array (e.g., to set a thermostat setpoint).
* A **commandable BV** object that supports writes (e.g., to turn a fan on or
  off).

Running the script starts a BACnet/IP server bound to UDP port 47808—the
default BACnet port—so ensure no other BACnet
applications are running.  The server updates the read‑only values every
few seconds.  You can then connect using another BACpypes 3 script to
read and write properties.

## How to Use It

1. **Run the mini device** – From the repository root, start the server:
   ```bash
   python3 mini-device-revisited.py --name MiniDevice --instance 1234
   ```
   The script will log that four objects (two read‑only and two
   commandable) have been registered.  Leave this process running.

2. **Inspect the objects** – Open a new terminal and write a small Python
   script that uses BACpypes 3 to read the `presentValue` of the
   `analogValue,1` and write to `binaryValue,2`.  Here is a simple
   example that toggles the commandable binary based on the read‑only
   analog value:
   ```python
   import asyncio
   from bacpypes3.app import Application
   from bacpypes3.argparse import SimpleArgumentParser
   from bacpypes3.pdu import Address
   from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest

   async def control_loop():
       parser = SimpleArgumentParser()
       args = parser.parse_args(args=[])
       app = Application.from_args(args)
       target = Address("localhost")
       while True:
           # Read the read‑only analog value
           rreq = ReadPropertyRequest(
               objectIdentifier=("analogValue", 1),
               propertyIdentifier="presentValue",
               destination=target,
           )
           value = await app.read_property(rreq)
           pv = value
           # Control the commandable binary: turn on if AV > 2.5
           new_state = "active" if pv > 2.5 else "inactive"
           wreq = WritePropertyRequest(
               objectIdentifier=("binaryValue", 2),
               propertyIdentifier="presentValue",
               propertyValue=new_state,
               destination=target,
           )
           await app.write_property(wreq)
           print(f"Read AV={pv:.1f}, set BV2 to {new_state}")
           await asyncio.sleep(5)

   asyncio.run(control_loop())
   ```
   This script reads the temperature value every five seconds and writes
   `active` to the commandable BV if the temperature exceeds 2.5 °F,
   otherwise it writes `inactive`.

3. **Experiment with algorithms** – Modify the control loop to implement
   a simple HVAC control strategy, such as adjusting the commandable AV
   setpoint based on the read‑only AV or toggling the BV in patterns.

## Why This Matters

Modern building automation systems rely on BACnet to exchange sensor and
actuator data.  Running a mini server locally lets you practise
interacting with BACnet objects without needing a real device.  Writing
algorithms to control commandable points mimics how thermostats or VAV
controllers respond to sensor readings and forms a bridge between
programming fundamentals and real‑world HVAC control.

## Mini Examples

* Start the server and observe that the read‑only AV ramps its
  `presentValue` every few seconds.
* Write a script that logs the values of all four objects every
  10 seconds.
* Modify the server code to add another commandable Analog Value object
  representing a supply air temperature setpoint and write to it from
  your control script.

## Micro Exercises

1. Extend the control loop so that it **writes** to `analogValue,2`
   whenever the read‑only binary object is `active`.  Choose a sensible
   setpoint value.
2. Use the BACpypes 3 `who_is` function to discover the mini device on
   your local network.  How does the device respond?
3. Edit `mini-device-revisited.py` to change the update interval from
   5 seconds to 2 seconds.  Restart the server and observe how the
   control loop responds.
4. Research how to read the **priority array** of the commandable
   objects.  What does it reveal about which values take precedence?

## Key Takeaway

By running a miniature BACnet server and controlling its commandable
points, you get hands-on experience with building automation concepts and
practise writing algorithms that respond to real-time data. This
exercise strengthens your understanding of Python loops, conditionals
and network I/O in a practical HVAC context.

---

## Vibe Code Checkpoint 5 (Week 5 / Bonus)

Run the **mini-device-revisited** and **mini-schedule-calendar-device** scripts. Write simple control logic against commandable points — e.g. read analogValue,1 and write to binaryValue,2 based on a threshold. Day 37 adds the schedule/calendar device for occupancy and holiday logic. These are the BACnet server patterns you'll use in the final project.
