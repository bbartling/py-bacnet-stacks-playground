# Py BACnet Stacks Playground

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white)](https://discord.gg/Ta48yQF8fC)



## **Applied Python + BACnet + Edge Automation for HVAC Controls Technicians, IoT Practitioners, and Building-Systems Tinkerers**

Welcome to the **Py BACnet Stacks Playground** — a hands-on, applied repository that starts with Python fundamentals and direct BACnet scripting, then evolves into **AI-assisted edge automation demos**.

The early *vibe code* apps stay grounded in **Python, BAC0, and BACpypes3**, where you build practical tools by directly interacting with BACnet devices—reading values, writing commands, inspecting priority arrays, and understanding real control behavior in the field.

From there, the project naturally expands into **VOLTTRON-based edge workflows**, where lightweight agents, platform services, and supervisory logic run continuously on a Raspberry Pi or edge gateway—bringing your scripts closer to real-world building automation deployments.

---

### 🤖 AI-Assisted Workflows (New Direction)

This repository also doubles as **model context for AI-assisted development**, enabling tools like Open Claw to:

* Bootstrap environments (e.g., VOLTTRON installs, BACnet apps) automatically
* Generate and refine BACnet scripts and edge agents
* Assist with debugging, testing, and system setup
* Orchestrate multi-step workflows across the stack

The goal is simple:
👉 let AI handle the repetitive, time-consuming setup and glue code
👉 while you focus on **control logic, system behavior, and engineering insight**

---

### 🚀 Where This Is Headed

* Python → BACnet fundamentals → real device interaction
* Edge deployment → VOLTTRON agents → continuous operation
* AI integration → faster builds, smarter workflows, less manual setup

Ultimately, this repo becomes a **playground for building smarter buildings faster**—combining:

* Hands-on HVAC controls knowledge
* Open protocols like BACnet
* Edge computing
* And AI-driven development workflows


---

## Who This Is For

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet from the field and wants to code it in Python and play around with AI!

---


## What You Will Learn

### Python (Applied Comp Sci 101)

- Variables, arithmetic, strings, lists, dictionaries
- Conditionals, loops, functions, modules, file I/O
- Error handling with `try`/`except`
- Simple algorithms: linear search, min/max, basic sorting
- Basic objects and instances (no advanced OOP)

**Scope:** Strings, lists, and dictionaries only. No advanced Python practices of list/dictionary comprehensions. No advanced data structures. See the `lessons` directory for the daily mini challenges and some of the YouTube videos demo theory lectures.

---


## Vibe Code Checkpoints

> **Current status:** **Checkpoint 10** — diy-bas integration (**Week 10**, current). **Checkpoint 11** (**Week 11**) — vibe app production cutover: Django with a production-grade database, React front end, SMTP, and user/role services. **Checkpoint 12** — hardening (**Week 12**). **Checkpoint 13** — final release.
> The project is moving from standalone demos into a full supervisory BAS-style application with a clearer multi-week path.

| # | Checkpoint | Build Goal | Timeline | Status |
| --- | --- | --- | --- | --- |
| **1** | **BAC0 + bacpypes3 basics** | Read `present-value`, write points, release with `NULL`, and learn priority arrays. | **Week 1** | Done |
| **2** | **RPM apps** | Use `ReadPropertyMultiple` across devices, log to CSV, and rotate daily files. | **Week 2** | Done |
| **3** | **Priority array tools** | Parse `priority-array`, inspect overrides, and understand control authority. | **Week 3** | Done |
| **4** | **BACnet server apps** | Build a mini BACnet device with schedule/calendar objects and weather server inputs. | **Week 4** | Done |
| **5** | **Device discovery tools** | Implement `Who-Is` / `I-Am` scanning and device enumeration. | **Week 5** | Done |
| **6** | **VOLTTRON deployment exploration with OpenClaw** | Explore deploying VOLTTRON with OpenClaw support, test the environment setup, and investigate how AI-assisted workflows can help scaffold edge BAS/FDD applications. | **Week 6** | Done |
| **7** | **VOLTTRON v9 BAS-style web agent** | Build and test a VOLTTRON v9 web agent with BACnet integration, mimicking a lightweight BAS supervisory interface. | **Week 7** | Done |
| **8** | **BAS schedule widget demo** | Build out a BAS-style schedule widget and frontend UI concepts. | **Week 8** | Done |
| **9** | **diy-bas beginning phase** | Create the first primitive version of the `diy-bas` application. | **Week 9** | Done |
| **10** | **diy-bas integration** | Combine authentication, alarms, schedules, trends, and BACnet discovery. | **Week 10** | **Current** |
| **11** | **diy-bas: Django production DB, unit tests, React front end, SMTP, role services** | Move the supervisory app toward production: managed database (e.g. PostgreSQL), **unit/integration tests** for critical paths, React UI shell, outgoing **SMTP** for notifications/alerts, and clearer **user/role services** (auth, RBAC, and integration boundaries). | **Week 11** | Next |
| **12** | **diy-bas hardening** | Add persistence depth, audit logging polish, security cleanup, and deploy/ops workflows beyond the initial integration. | **Week 12** | Next |
| **13** | **diy-bas final app release** | Ship the Raspberry Pi-ready supervisory BAS application. | **Final** | Planned |
| **14** | **Rust BACnet stack** | Bonus: integrate [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) with Python bindings. | **Bonus** | TODO |
| **15** | **Protocol debugging** | Bonus: use Wireshark and Linux tools to validate BACnet/IP behavior. | **Bonus** | TODO |


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


## License

MIT License — use, remix, share forward. Built for the BAS community.
