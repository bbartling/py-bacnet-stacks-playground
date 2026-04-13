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

## Open Claw Model Routing Prompt

Just drop this prompt right into Open Claw—it’s helped me avoid hitting API limits. I think it encourages the framework to use simple, low-cost models for easier tasks, while reserving more advanced (and expensive) models only for the tasks that truly require deeper reasoning.


```text
## Model Routing Policy
When analyzing test results, classify each task before processing:
SIMPLE (use primary model):
- Pass/fail test results
- HTTP status code errors (404, 500, timeout)
- Missing UI elements or broken selectors
- Test environment setup failures
- Syntax errors or import failures
COMPLEX (use thinking model)
- Unexpected behavior that passed but shouldn't have
- Race conditions or timing-dependent failures
- Security vulnerabilities
- Performance degradation patterns
- Failures that span multiple components or files
Default to SIMPLE unless the test result shows ambiguous or multi-layered behavior.
Always classify first, then process. Never use the thinking model for a task that fits the SIMPLE list.

```


---


## Vibe Code Checkpoints

| Checkpoint    | What to Build                                                                                                                                       | When       |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| **1**         | **BAC0 + bacpypes3 basics:** read `present-value`, write to a point, write null (release), understand commandable objects + priority levels         | **Week 1** |
| **2**         | **RPM apps (BAC0 + bacpypes3):** ReadPropertyMultiple across devices, log to CSV, implement daily rotation (`csv` module)                           | **Week 2** |
| **3**         | **Priority Array tools:** read + parse `priority-array`, inspect overrides, understand control authority                                            | **Week 3** |
| **4**         | **BACnet server apps:** mini device, schedule/calendar objects, weather server using OpenWeatherMap                                                 | **Week 4** |
| **5**         | **Device discovery tools:** Who-Is / I-Am scanning, device enumeration (BAC0 + bacpypes3)                                                           | **Week 5** |
| **6**         | **COV monitoring apps:** subscribe to Change-of-Value, stream live updates from devices                                                             | **Week 6** |
| **7**         | **Open Claw + VOLTTRON bootstrap:** auto-provision VOLTTRON on edge (e.g., Raspberry Pi), build a simple BAS/BMS-style GUI (lightweight “vibe app”) | **Week 7** |
| **8** *(current)* | **BAS Lite (Vibe App 8):** newest stack in **`vibe_code_apps_8`** — React/TypeScript UI built into the VOLTTRON web agent, Platform Driver–aligned APIs, optional Caddy on :80, site-model JSON for any building/LAN topology (`docs/replicate-any-building-lan-topology.md`). Evolves Week 7 into a production-style edge dashboard. | **Week 8** |
| **9** | **VOLTTRON Central + Timescale + Forward (ZMQ):** **`vibe_code_apps_9`** — fresh **Ubuntu** central with **SQLHistorian** ([Timescale](https://volttron.readthedocs.io/en/main/volttron-api/services/SQLHistorian/README.html)), **VolttronCentralPlatform** + **VolttronCentral** ([VC stack](https://volttron.readthedocs.io/en/main/volttron-api/services/VolttronCentral/modules.html)), **boss Pi** with **ForwardHistorian** ([multi-platform ZMQ](https://volttron.readthedocs.io/en/main/deploying-volttron/multi-platform/forward-historian-deployment.html)); Docker TimescaleDB. Tutorial: `vibe_code_apps_9/docs/volttron-central-forward-timescale-tutorial.md`. | **Week 9** |
| **10**        |                                                                                                                                                     |            |
| **11**        |                                                                                                                                                     |            |
| **12**        |                                                                                                                                                     |            |
| **13** *(TODO)* | **Rust BACnet stack:** integrate [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) with Python bindings, rebuild key apps using a Rust backend | **Future** |
| **14** *(TODO)* | **Protocol debugging:** Wireshark + Linux tooling, inspect BACnet/IP traffic, validate and troubleshoot all apps built                              | **Final**  |

---

### Notes / Direction

* **Checkpoint 8** is the live edge dashboard: **`vibe_code_apps_8`**, tutorial `vibe_code_apps_8/docs/bas-lite-app8-tutorial.md`.
* **Checkpoint 9** is multi-platform centralization: **`vibe_code_apps_9`**, tutorial `vibe_code_apps_9/docs/volttron-central-forward-timescale-tutorial.md`.
* Checkpoints **10–12** are intentionally open for future vibe apps.
* Week 7–8 is where things get **really interesting** → agentic workflows + real BAS-style UI
* Open Claw becomes your **automation layer** (bootstrapping, testing, orchestration)
* React + Caddy introduces **real-world web architecture patterns**
* **Checkpoint 13** ([rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)) + **checkpoint 14** (Wireshark) = **next-level protocol + performance understanding**


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
