# Py BACnet Stacks Playground

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white)](https://discord.gg/Ta48yQF8fC)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/bbartling/py-bacnet-stacks-playground)](LICENSE)
[![BACnet edge + FDD](https://img.shields.io/badge/active-vibe__code__apps__12-009966)](vibe_code_apps_12/)
[![Docs PDF](https://img.shields.io/badge/docs-PDF%20manual-blue)](vibe_code_apps_12/pdf/vibe12-edge-fdd-guide.pdf)
[![AWS IoT Core](https://img.shields.io/badge/cloud-AWS%20IoT%20Core-FF9900?logo=amazonaws&logoColor=white)](vibe_code_apps_12/aws_cloud_pipeline/)

## **Applied Python + BACnet + Edge Automation for HVAC Controls Technicians, IoT Practitioners, and Building-Systems Tinkerers**

Welcome to the **Py BACnet Stacks Playground** — a hands-on, applied repository that starts with Python fundamentals and direct BACnet scripting, then evolves into **AI-assisted edge automation demos**.

The early *vibe code* apps stay grounded in **Python, BAC0, and BACpypes3**, where you build practical tools by directly interacting with BACnet devices—reading values, writing commands, inspecting priority arrays, and understanding real control behavior in the field.

From there, the project is now exploring AI-driven workflows for bootstrapping VOLTTRON-based edge systems and building a BAS from scratch through web app development.

The goal is to experiment with lightweight agents, platform services, and supervisory logic running continuously on a Raspberry Pi or edge gateway, bringing simple scripts closer to real-world building automation deployments.

Come join the journey as we play around with Python, AI, BACnet, and computer science theory in a fun, hands-on playground designed for learning. This series is geared toward people with little to no technical background beyond real-world field experience as building automation technicians.


---

## Who This Is For

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet from the field and wants to code it in Python and play around with AI!

---


## Vibe Code Checkpoints

Hands-on milestones from BACnet scripting to cloud FDD. **Featured builds** are linked below; checkpoints **1–10** are historical demos.

| # | Checkpoint | Summary | Status |
| --- | --- | --- | --- |
| **1** | **BAC0 + bacpypes3 basics** | Read/write `present-value`, release with `NULL`, priority arrays. | Done |
| **2** | **RPM apps** | `ReadPropertyMultiple` across devices; CSV logs with daily rotation. | Done |
| **3** | **Priority array tools** | Parse `priority-array`, inspect overrides, control authority. | Done |
| **4** | **BACnet server apps** | Mini BACnet device: schedules, calendars, weather server inputs. | Done |
| **5** | **Device discovery tools** | `Who-Is` / `I-Am` scanning and device enumeration. | Done |
| **6** | **VOLTTRON + OpenClaw exploration** | VOLTTRON deploy experiments; AI-assisted edge BAS/FDD scaffolding. | Done |
| **7** | **VOLTTRON v9 BAS-style web agent** | BACnet-integrated supervisory web agent on VOLTTRON v9. | Done |
| **8** | **BAS schedule widget demo** | Schedule widget and frontend UI concepts. | Done |
| **9** | **diy-bas — beginning phase** | First `diy-bas` shell: **Flask** API + vanilla JS UI. | Done |
| **10** | **diy-bas — integration** | Auth, alarms, schedules, trends, discovery in **Django + React** (superseded by **11**). | Done |
| **11** | **[Agentic BAS from spec](https://github.com/bbartling/py-bacnet-stacks-playground/tree/develop/vibe_code_apps_11)** | **Paused.** Spec-driven BAS via **SKILL.md**, workspace memory, and cron-driven **Codex CLI** agent (drivers, commissioning, web app). | Paused |
| **12** | **[AI-assisted edge-to-cloud HVAC FDD](https://github.com/bbartling/py-bacnet-stacks-playground/tree/develop/vibe_code_apps_12)** | **Active featured build.** End-to-end HVAC fault detection pipeline: BACnet discovery, commissioning CSVs, RPM polling, AWS IoT Core MQTT, DynamoDB historian, Lambda dashboard, Python FDD Rule Lab, Brick-style data modeling, and AI-assisted development workflows. | **Active** |
| **13** | **DIY BACnet router** *(planned)* | Pi/Linux **BACnet/IP ↔ MS/TP** router using **bacnet-stack** `router-mstp`; informed by app **14**. Slot: `vibe_code_apps_13/`. | Planned |
| **14** | **[BACnet routing research lab](https://github.com/bbartling/py-bacnet-stacks-playground/tree/develop/vibe_code_apps_14)** | **Active.** BACpypes3 timed labs (dual [mini-device](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py), [ipv4 router](https://github.com/JoelBender/BACpypes3/blob/main/samples/ipv4-to-ipv4.py), pcaps) toward [Misty3](https://github.com/raghavan97/misty3) and [router-mstp](https://github.com/bacnet-stack/bacnet-stack/tree/master/apps/router-mstp). | **Active** |
| **15** | **STM32 bare-metal BACnet device** *(planned)* | Embedded **C** BACnet stack on **STM32**; MS/TP or UART as hardware allows. | Planned |
| **16** | **Rust BACnet stack** *(planned)* | [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) + Python bindings; benchmarks beside BACpypes3. | Planned |
| **17** | **[Project Haystack playground](vibe_code_apps_17/)** | Niagara **nHaystack** Pi lab, [`rusty-haystack`](https://github.com/jscott3201/rusty-haystack) (Rust client/server + PyO3), and [`pyhaystack`](https://github.com/ChristianTremblay/pyhaystack) (Python). | **Active** |



---

## Computer Science Theory 101 Weekly Outline

These are AI-generated mini lessons designed as daily challenges, starting at the complete beginner level and progressing all the way through algorithms such as Guideline 36 and advanced data structures, eventually getting into RDF theory for smart building data modeling standards such as Brick, Haystack, and ASHRAE 223P.


### Week 1 — Fundamentals & First BACnet App  
*Part I: Variables, operators, strings, numbers, booleans, input/output, lists*

- **Day 1 — Installing Python & Pip (BACnet Ready):** Set up Python, pip, BAC0, bacpypes3.
- **Day 2 — Variables & Arithmetic:** Store values, arithmetic, operator precedence.
- **Day 3 — Working with Strings:** Create, concatenate, index, slice strings.
- **Day 4 — Numbers, Booleans & Comparisons:** Numeric types, comparisons, truthiness.
- **Day 5 — User Input & Output:** `input()`, type conversion, f-strings.
- **Day 6 — Introducing Lists:** Create, index, slice, append, `len()`.
- **Day 7 — List Operations & Methods:** append, extend, insert, remove, sort, copy.

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

---

### Week 4 — Data Structures & Discovery  
*Part III: Lists, dicts, file I/O*

- **Day 22 — Working with Nested Data:** Lists of dicts, dicts of lists (loops only, no comprehensions).
- **Day 23 — Random & Math:** `random`, `math` for simulations.
- **Day 24 — any(), all() & Simple Patterns:** Boolean checks on collections.
- **Day 25 — Documentation & help():** Docstrings, comments, `help()`.
- **Day 26 — Week 4 Review:** Nested data, built-ins, loops.

---

### Week 5 — Algorithms & HVAC Data (Part A)  
*Part IV: Search, sort, strings, membership*

- **Day 27 — What Is an Algorithm? (HVAC & data):** Finite steps, inputs/outputs, course framing.
- **Day 28 — Linear Search:** First match / threshold scans on trend-like lists.
- **Day 29 — Min & Max:** Accumulator scans on readings.
- **Day 30 — Counting Occurrences:** Frequency tables (fault codes, equipment types).
- **Day 31 — Sorting & Median:** `sorted()`, keys, median; bubble sort as pedagogy only.
- **Day 32 — String Parsing for BAS Text:** `split`, `join`, `strip` for exports and tags.
- **Day 33 — Membership & Index Search:** `in` vs explicit loops for position.

---

### Week 6 — Algorithms, FDD Logic, Thermal Lite, Capstone (Part B)  
*Part IV continued: stats, Boolean FDD patterns, R–C + Euler, no Pandas*

- **Day 34 — Aggregates:** Mean, median, short HVAC samples.
- **Day 35 — Fault Detection as Boolean Logic:** Thresholds, AND/OR/NOT (open-fdd *expression* mindset; plain Python).
- **Day 36 — Deadbands & Envelopes:** Chattering, MAT vs OAT/RAT band (high-level).
- **Day 37 — Sliding Windows:** Running mean/max with list slices (no Pandas).
- **Day 38 — Thermal R–C Analogy:** One-node intuition for building dynamics.
- **Day 39 — Explicit Euler:** Integrate a 1-state toy thermal model in a loop.
- **Day 40 — Capstone:** Parallel lists + simple fault timeline + course self-check.

---

### Week 6b — GL36 Trim & Respond (Python, from working Java/Niagara blocks)  
*After Day 40 capstone; mirrors [n4-hvac-optimization-blocks](https://github.com/bbartling/n4-hvac-optimization-blocks) GL36 logic in plain Python*

- **Day 41 — VAV zone requests:** GL36 variable table; cooling + duct static **0–3** request counters (`vavCoolRequests`, `vavPressureRequests`).
- **Day 42 — AHU duct static T&R:** Fan gating, startup delay **Td**, trim/respond on summed pressure requests **R**.
- **Day 43 — AHU SAT T&R:** `tMax` trim/respond + OAT interpolation curve for discharge air temperature.
- **Day 44 — Chiller plant enable:** AHU CHW valve latches, min ON/OFF, `chillerEnableCommand`.
- **Day 45 — Central plant AHU request counter:** SAT error ladders → cooling/heating **0–3** for plant resets.
- **Day 46 — HWST Trim & Respond:** Hot water supply reset from aggregated heating requests.
- **Day 47 — CHW Trim & Respond:** Single **0–100%** loop → DP reset (0–50%) then CHWST reset (50–100%).


---

### Week 7 — Python Bridge for RDF (Smart Buildings)  
*Only structures needed later: identity, nesting, uniqueness, tiny “graphs”*

- **Day 48 — Buildings as Graphs, Not Only Tables:** Rows vs relationships; why BAS interoperability uses graphs.
- **Day 49 — URIs & IRIs as Identity:** Strings that name things globally; cool URI vs literal.
- **Day 50 — Prefix Maps:** `dict` from prefix string to base IRI; expand `brick:AHU` by hand.
- **Day 51 — Triples as Data:** `(subject, predicate, object)` tuples; `list` of triples as a toy graph.
- **Day 52 — Literals vs Resources:** When the object is a typed value (lexical + datatype name as strings).
- **Day 53 — Adjacency-Style `dict`:** `subject -> list` of `(predicate, object)` pairs (simple directed multigraph).
- **Day 54 — From Rows to Nodes:** Nested `dict` records for one equipment + points (bridge from CSV/BACnet thinking).

---

### Week 8 — RDF & Turtle (Theory + `rdflib`)  
*Triple model, syntax, loading graphs in Python*

- **Day 55 — RDF Triple Model:** Subject, predicate, object; blank nodes mentioned lightly.
- **Day 56 — `rdf:type` & Taxonomy:** Instance of a class; `rdfs:subClassOf` as “is-a” chain (concept + tiny triples).
- **Day 57 — Properties:** `rdf:Property`; domain and range (read diagrams / docs, not proofs).
- **Day 58 — Reading Turtle:** `.` `;` `,` blocks; prefixes; comments.
- **Day 59 — `rdflib` Graph from Turtle:** Parse a string; count triples; iterate `graph.triples(...)`.
- **Day 60 — Serialization:** `graph.serialize(format="turtle")`; round-trip sanity check.
- **Day 61 — Merging Graphs:** Add triples from two sources; dedupe with a `set` of frozen rows (pattern only).

---

### Week 9 — Brick Ontology on RDF  
*Classes and relationships for equipment and points*

- **Day 62 — `brick:` Namespace:** What Brick adds on top of RDF/RDFS.
- **Day 63 — Equipment Taxonomy:** AHU, VAV, chiller as classes; subclass chains at high level.
- **Day 64 — Key Predicates:** `brick:hasPoint`, `brick:isPartOf`, `brick:feeds` (meanings, not every term).
- **Day 65 — Hand-Author a Tiny Model:** Write Turtle for one AHU + one SAT sensor (by hand, then optional parse check).
- **Day 66 — Haystack Tags vs Brick Graphs:** When tags are enough vs when you need a mergeable RDF model.
- **Day 67 — FDD & Ontology:** How rule `inputs` (e.g. open-fdd) map to Brick-class *names* as logical columns (conceptual).

---

### Week 10 — SPARQL for Brick Graphs  
*Patterns, filters, optional data, capstone query*

- **Day 68 — Why SPARQL:** Graph pattern matching; WHERE block as “shape to find.”
- **Day 69 — `SELECT` & Basic `WHERE`:** Variables `?x`; one- and two-triple patterns on `rdflib` data.
- **Day 70 — `FILTER` & `BIND`:** Numeric comparisons; computed columns in result rows.
- **Day 71 — `OPTIONAL`:** Points that may be missing; null-like unbound variables.
- **Day 72 — `UNION`:** Alternative patterns (this OR that equipment layout).
- **Day 73 — `ASK`:** Existence checks for commissioning rules (“is there any…?”).
- **Day 74 — `DISTINCT`, `ORDER BY`, `LIMIT`:** Practical query hygiene on building models.
- **Day 75 — Capstone:** Multi-clause `SELECT` on a small Brick TTL file bundled with the lesson; document what you queried.

---


## License

MIT License — use, remix, share forward. Built for the BAS community ❤️🥰.
