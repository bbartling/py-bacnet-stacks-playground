# Day 37 – Scheduling with a Mini BACnet Calendar Device

## Goal

Run the `mini-schedule-calendar-device.py` script to simulate a simple
scheduling and holiday calendar, inspect the schedule and calendar
objects, and write Python code to read the schedule’s `presentValue`
and weekly schedule via BACnet.  You will practise working with
time‑based control and understand how building automation systems
schedule occupancy.

## Concept

The `mini-schedule-calendar-device.py` script creates a BACnet server
that exposes three objects:

* A **Calendar** object (`calendar,1`) that holds dates for holidays.
* A **Schedule** object (`schedule,1`) that defines a weekly schedule
  (Monday to Friday 8:00–17:00 on, weekends off) with an exception
  list for holidays.
* A **Binary Value** object (`binaryValue,1`) that mirrors the schedule’s
  `presentValue`—it is `active` when the schedule is on.

The schedule’s `presentValue` updates automatically based on the
current date and time.  Reading the weekly schedule via BACnet
requires sending a `ReadPropertyRequest` for the `weeklySchedule`
property.  Writing to the schedule or calendar is more advanced and
requires understanding the BACnet `ScheduleObject` and `CalendarObject`.

## How to Use It

1. **Start the schedule device** – Run the script in a terminal:
   ```bash
   python3 mini-schedule-calendar-device.py --name ScheduleTest --instance 5678
   ```
   The server registers the calendar, schedule and BV objects.

2. **Read the schedule present value** – In a separate Python script,
   use BACpypes 3 to read the `presentValue` of the schedule.  The
   request is similar to Day 36 but uses a different object
   identifier:
   ```python
   import asyncio
   from bacpypes3.app import Application
   from bacpypes3.argparse import SimpleArgumentParser
   from bacpypes3.pdu import Address
   from bacpypes3.apdu import ReadPropertyRequest

   async def read_schedule():
       app = Application.from_args(SimpleArgumentParser().parse_args(args=[]))
       target = Address("localhost")
       rreq = ReadPropertyRequest(
           objectIdentifier=("schedule", 1),
           propertyIdentifier="presentValue",
           destination=target,
       )
       value = await app.read_property(rreq)
       print("Schedule present value =", value)
       # Read the weekly schedule (returns an array of DailySchedule)
       rreq_week = ReadPropertyRequest(
           objectIdentifier=("schedule", 1),
           propertyIdentifier="weeklySchedule",
           destination=target,
       )
       weekly = await app.read_property(rreq_week)
       print("Weekly schedule:", weekly)

   asyncio.run(read_schedule())
   ```
   The `weeklySchedule` property returns a list of seven daily schedules
   (Monday–Sunday).  Each `DailySchedule` contains a list of `(time,
   value)` entries.  You can parse this to generate an occupancy
   timetable.

3. **Experiment with the schedule** – Change the start and end times in
   `mini-schedule-calendar-device.py` (see the `build_weekly_schedule()`
   function) to adjust office hours.  Restart the server and verify that
   the schedule `presentValue` reflects your new hours.

## Why This Matters

Real BAS controllers use schedules and calendars to control equipment
based on occupancy and holidays.  Understanding how to read and
interpret schedule objects via BACnet is essential for writing
algorithms that adapt HVAC operation to time of day.  The mirroring
binary value demonstrates how other objects can listen to a schedule and
react accordingly.

## Mini Examples

* Run the script and read the schedule’s `presentValue` every minute
  for an hour.  Observe how it toggles between `0` and `1` based on
  time of day.
* Modify the holiday calendar to include another date (e.g., your
  birthday) and verify that the schedule turns off on that date.
* Write a function that generates a human‑readable summary of the
  weekly schedule using the `weeklySchedule` property.

## Micro Exercises

1. Use the `CalendarObject` to add a new holiday date to the
   `holiday_calendar` in the script.  How does this affect the
   schedule’s `presentValue`?
2. Write Python code that, given a date and time, determines whether
   the schedule is active or inactive based solely on the `weeklySchedule`
   property (ignore holidays).
3. Modify the schedule so that it turns on at 7:30 AM instead of
   8:00 AM.  Restart the server and confirm the change.
4. Explore BACpypes 3 documentation to find out how to write a new
   exception event into the `exceptionSchedule` list.  (Hint: you need
   to write an array of `SpecialEvent` structures.)

## Key Takeaway

Scheduling and calendar objects are fundamental to building control
systems.  Running a mini schedule device and reading its properties
teaches you how BACnet represents time‑based control logic and how to
interact with these objects programmatically.  You will apply similar
techniques when modelling schedules in more advanced semantic models.
