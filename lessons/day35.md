# Day 35 – Final Project: Web Weather Station BACnet Server

*Part IV: Objects & Algorithms | Week 5*

## Goal

Today you will build the **final project**: a **Web Weather Station BACnet Server**. Fetch weather data from the Open Weather Map API, expose it as BACnet objects (analog values, etc.), and run a mini BACnet server. This ties together everything you have learned: HTTP requests, parsing JSON, BACnet server objects, and Python data structures.

## Concept

A BACnet server exposes objects that clients can read. The Open Weather Map API returns JSON with temperature, humidity, pressure, etc. Your app will: (1) fetch weather data via HTTP, (2) parse the JSON into Python dicts, (3) create BACnet Analog Value objects with present-value set from the API, (4) run a BACpypes3 Application that serves these objects. Use the mini-device-revisited pattern — add AnalogValueObject instances, update their presentValue periodically from the API.

## How to Use It

**Ideas (no full code — you vibe code it):**

1. Use `urllib.request` or the `requests` library to call the Open Weather Map API. You need an API key (free tier).
2. Parse the JSON response into a dictionary. Extract `main.temp`, `main.humidity`, `main.pressure`, etc.
3. Create BACpypes3 AnalogValueObject instances for each weather metric. Register them with your Application.
4. Run a loop that fetches the API every few minutes and updates each object's presentValue.
5. Run the server; use a BACnet client or scanner to read the weather objects.

## Why This Matters

This project combines HTTP, JSON, dictionaries, loops, and BACnet servers. It demonstrates how external data (weather) can be exposed as BACnet points — a common pattern for integrating third-party APIs into building automation.

## Mini Examples

- Start with the mini-device-revisited structure. Replace the simulated ramp with an HTTP fetch to Open Weather Map.
- Add one AnalogValueObject for temperature. Update it every 5 minutes from the API.
- Extend to humidity, pressure, and any other metrics you want to expose.

## Micro Exercises

1. Add error handling: if the API request fails, keep serving the last known values.
2. Add a description property to each object so clients see "Outdoor Temperature" etc.
3. Consider adding units (degreesFahrenheit, percentRelativeHumidity, etc.).

## Key Takeaway

The final project ties together HTTP, JSON, dictionaries, and BACnet servers. You fetch real-world data and expose it as BACnet objects — a powerful pattern for HVAC and IoT integration.
