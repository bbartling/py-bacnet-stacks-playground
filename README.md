# Py BACnet Stacks Playground

**Applied Python + BACnet for HVAC Controls Technicians & IoT Practitioners**

Welcome to the **Py BACnet Stacks Playground** — a hands-on course that teaches Python fundamentals while you build real BACnet applications. Each day you'll study applied computer science in Python (easy 101 level) and vibe code a BACnet app that matches the pace of the lesson plan. No deep dives into the BACnet spec or bytes-on-the-wire networking — just Python, BAC0, and BACpypes3 doing the heavy lifting while you focus on building useful tools.

---

## Who This Is For

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet from the field and wants to code it in Python

**What this is NOT:** An advanced networking course. Not a low-level BACnet protocol / bytes-on-the-wire programming course. We stay in the Python world — BAC0 and BACpypes3 handle BACnet conversions for you.

---

## Go Above & Beyond — Earn a Real Badge

This applied course gets you building BACnet apps fast and focuses on practical, hands-on skills you can use immediately. To go deeper and earn a **professional certificate you can add to your LinkedIn**, consider the **Georgia Institute of Technology Introduction to Python Programming Professional Certificate** offered through **edX**. It follows a similar learning style—short videos and hands-on exercises—but provides a formal, recognized credential at the end.

After completing this course and that certificate, adding **Linux fundamentals** rounds out the full skill set. Linux command-line and operating system knowledge is essential in OT, IoT, and building automation environments, where edge devices, gateways, servers, containers, and embedded systems commonly run Linux. Combining Python, Linux, networking, and data skills positions you to work comfortably across both IT and OT systems and makes you significantly more valuable in modern smart-building roles.

Together, these skills form a complete, highly marketable foundation for automation, controls, and edge computing careers:

* **Linux & Systems** — command line, processes, networking, Docker, edge devices, Raspberry Pi/industrial gateways
* **IT & IoT** — network automation, device integration, building systems, BACnet/Modbus/MQTT
* **Databases** — storing and querying sensor data, time-series storage, analytics pipelines
* **Machine Learning & Data Science** — forecasting, anomaly detection, fault detection (FDD), optimization
* **Software Engineering** — APIs, web apps, testing, CI/CD, and production deployments


---


## What You Will Learn

### Python (Applied Comp Sci 101)

- Variables, arithmetic, strings, lists, dictionaries
- Conditionals, loops, functions, modules, file I/O
- Error handling with `try`/`except`
- Simple algorithms: linear search, min/max, basic sorting
- Basic objects and instances (no advanced OOP)

**Scope:** Strings, lists, and dictionaries only. No list/dictionary comprehensions. No advanced data structures.

### BACnet Applications

- **BAC0:** Read, write, write null release, Who-Is discovery, data collection
- **BACpypes3:** Same workflows in raw BACpypes — read, write, release, discover to CSV
- **BACnet servers:** Mini device, mini schedule/calendar device
- **Final project:** Web weather station — Open Weather Map API → BACnet objects as a server

---

## Course Structure

Inspired by the EdX *Computing in Python* series. Four parts plus bonus:

| Part | Focus | Vibe Code Checkpoint |
|------|-------|----------------------|
| **Part I — Fundamentals** | Variables, operators, strings, numbers, booleans, input/output, lists | **Checkpoint 1:** BAC0 app that reads, writes, and writes null release |
| **Part II — Control Structures** | Loops, conditionals, functions, modules, files, error handling | **Checkpoint 2:** BAC0 app that collects data, saves to CSV, rotates log files per day |
| **Part III — Data Structures** | Strings, lists, dictionaries, file I/O (no comprehensions) | **Checkpoint 3:** bacpypes3 read/write/release app; **Checkpoint 4:** BACnet discover → CSV (Who-Is, object list, name/description/present-value/units) |
| **Part IV — Objects & Algorithms** | Simple objects, linear search, min/max, basic sorting | **Checkpoint 5:** BACnet servers (mini device, mini schedule); **Final Project:** Web weather station BACnet server |
| **Bonus — Operations** | Wireshark, systemd, Docker | Troubleshooting BACnet/IP, deploying scrapers with systemd and Docker |

---

## Vibe Code Checkpoints

You vibe code each app on YouTube — no full solutions in the lessons. The course gives you **ideas and challenges** to meet at each checkpoint.

| Checkpoint                | What to Build                                                                                                                                                      | When       |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| **1**                     | **BAC0 + bacpypes3 apps:** read present-value, write to a point, write null release (commandable objects, priority levels)                                         | **Week 1** |
| **2**                     | **BAC0 + bacpypes3 RPM apps:** ReadPropertyMultiple (RPM) across multiple devices, save to CSV, daily log rotation (`csv` module)                                  | **Week 2** |
| **3**                     | **Priority Array inspection apps (BAC0 + bacpypes3):** read `priority-array`, parse values correctly, handle `_choice`, debug overrides, inspect control authority | **Week 3** |
| **4**                     | **BACnet Servers (BAC0 + bacpypes3):** run mini device, mini schedule/calendar device, implement simple control logic against commandable points                   | **Week 4** |
| **Final Project**         | Web Weather Station: fetch OpenWeatherMap API → expose as BACnet objects (custom BACnet server)                                                                    | **Week 5** |
| **Advanced / Operations** | Linux fundamentals, systemd service deployment, Docker containerisation, Wireshark BACnet/IP debugging, production hardening                                       | **Week 6** |




---

## Weekly Outline

### Week 1 — Fundamentals & First BACnet App  
*Part I: Variables, operators, strings, numbers, booleans, input/output, lists*

- **Day 1 — Installing Python & Pip (BACnet Ready):** Set up Python, pip, BAC0, bacpypes3.
- **Day 2 — Variables & Arithmetic:** Store values, arithmetic, operator precedence.
- **Day 3 — Working with Strings:** Create, concatenate, index, slice strings.
- **Day 4 — Numbers, Booleans & Comparisons:** Numeric types, comparisons, truthiness.
- **Day 5 — User Input & Output:** `input()`, type conversion, f-strings.
- **Day 6 — Introducing Lists:** Create, index, slice, append, `len()`.
- **Day 7 — List Operations & Methods:** append, extend, insert, remove, sort, copy.

**Checkpoint 1:** BAC0 app — read, write, write null release.

---

### Week 2 — Control Structures & Data Collection  
*Part II: Loops, conditionals, functions, files*

- **Day 8 — For Loops & Range:** Iterate over lists/strings/ranges, `enumerate()`.
- **Day 9 — Conditionals & While Loops:** `if`/`elif`/`else`, `while`, sentinel loops.
- **Day 10 — String Methods: Split, Join & Case:** `split()`, `join()`, case conversion.
- **Day 11 — Introducing Dictionaries:** Keys, values, add, retrieve, membership.
- **Day 12 — Looping over Dictionaries:** `items()`, `keys()`, `values()` (no comprehensions).
- **Day 13 — Tuples & Sets (Light):** Immutable tuples, sets for membership (optional).
- **Day 14 — Loops & Sentinels:** `break`, `continue`, common loop patterns.

---

### Week 3 — Functions, Modules & Files  
*Part II continued: Reusable code, modules, file I/O*

- **Day 15 — Writing Functions:** Define functions, parameters, return, docstrings.
- **Day 16 — Modules & the Standard Library:** `math`, `random`, organising code.
- **Day 17 — Reading & Writing Files:** `open()`, `with`, read/write text and CSV.
- **Day 18 — Handling Errors:** `try`/`except`, robust programs.
- **Day 19 — Week 3 Review:** CSV of sensor readings, statistics, error handling.
- **Day 20 — Built-in Functions:** `min()`, `max()`, `sorted()`, `sum()`, `zip()` (no comprehensions).
- **Day 21 — Slicing & String Formatting:** Advanced f-strings, slicing.

**Checkpoint 2:** BAC0 app — collect data, save to CSV, rotate logs per day.  
**Checkpoint 3:** bacpypes3 read/write/release app.

---

### Week 4 — Data Structures & Discovery  
*Part III: Lists, dicts, file I/O*

- **Day 22 — Working with Nested Data:** Lists of dicts, dicts of lists (loops only, no comprehensions).
- **Day 23 — Random & Math:** `random`, `math` for simulations.
- **Day 24 — any(), all() & Simple Patterns:** Boolean checks on collections.
- **Day 25 — Documentation & help():** Docstrings, comments, `help()`.
- **Day 26 — Week 4 Review:** Nested data, built-ins, loops.
- **Day 27 — What Is an Algorithm?:** Steps, efficiency, problem decomposition.
- **Day 28 — Linear Search:** Implement and analyse linear search.

**Checkpoint 4:** BACnet discover → CSV (Who-Is, object list, properties).

---

### Week 5 — Algorithms & BACnet Servers  
*Part IV: Simple algorithms, objects, final project*

- **Day 29 — Finding Min & Max:** Compute smallest/largest in a list.
- **Day 30 — Counting Occurrences:** Frequency tables with dictionaries.
- **Day 31 — Sorting Lists:** Basic sorting, `sort()` and `sorted()`.
- **Day 32 — String Algorithms:** Substring search, prefixes, suffixes.
- **Day 33 — Membership & Searching:** `in`, sets, dict lookups.
- **Day 34 — Aggregating Data:** Sums, averages, simple statistics.
- **Day 35 — Final Project:** Web weather station BACnet server.

**Checkpoint 5:** Mini BACnet device + mini schedule/calendar device.  
**Final Project:** Open Weather Map API → BACnet server.

---

### Week 6 — Bonus: Operations  
*Troubleshooting & deployment*

- **Day 36 — Playing with a Mini BACnet Device:** Run mini-device-revisited.py, read/write, simple control logic.
- **Day 37 — Scheduling with a Mini BACnet Calendar Device:** Run mini-schedule-calendar-device.py, read schedule/calendar.
- **Day 38 — Troubleshooting BACnet with Wireshark:** Capture BACnet/IP with tcpdump, inspect in Wireshark.
- **Day 39 — Deploying a CSV Scraper with systemd:** systemd service for auto-start and restart.
- **Day 40 — Containerising Your Scraper with Docker:** Docker container, restart policies.

---


## Using This Repository

- Lessons live in `lessons/` as `dayXX.md`.
- Each lesson has: Goal, Concept, How to Use It, Mini Examples, Micro Exercises, Key Takeaway.
- **Vibe code** your BACnet apps — lessons give ideas and checkpoints, not full app code.
- Work through one lesson per day; checkpoints align with the weekly outline.

---

## Reference Scripts (Not Course Code)

These exist elsewhere for reference; the course does not include their full code:

- `mini-device-revisited.py` — BACpypes3 mini BACnet server (read-only + commandable AV/BV).
- `mini-schedule-calendar-device.py` — BACpypes3 schedule + calendar device.
- `discover-objects-csv-only.py` — Who-Is → object list → CSV export.

---

## License

MIT License — use, remix, share forward. Built for the BAS community.
