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
- Simple algorithms: linear search, min/max, basic sorting; light HVAC fault-detection logic and a tiny thermal simulation (Days 27–40)
- **After Day 40:** graph-thinking for **smart buildings** — only the data structures needed to read **RDF**, relate it to **Brick**, and run **SPARQL** (Days 41–68). Still **no list/dict comprehensions** in lesson examples unless noted optional.

**Scope:** Early weeks: strings, lists, dictionaries. **Days 41–68:** tuples, sets, nested dicts, and simple **graph-as-data** patterns (adjacency-style dicts, lists of triples) *only* as scaffolding for RDF/Brick/SPARQL—not a full computer-science graph-algorithms course. See the `lessons` directory for daily mini-lessons; **[lessons/INDEX.md](lessons/INDEX.md)** links every day by week.

---


## Vibe Code Checkpoints

> **Current status:** **Checkpoint 10** — diy-bas integration (**Week 10**, current). **Checkpoint 11** (**Week 11**) — vibe app production cutover: Django with a production-grade database, React front end, **ntfy** (or similar) notifications, and user/role services. **Checkpoint 12** — hardening (**Week 12**). **Checkpoint 13** — final release.
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
| **11** | **diy-bas: Django production DB, unit tests, React front end, notifications, role services** | Move the supervisory app toward production: managed database (e.g. PostgreSQL), **unit/integration tests** for critical paths, React UI shell, outgoing **notifications** (e.g. ntfy) for alerts, and clearer **user/role services** (auth, RBAC, and integration boundaries). | **Week 11** | Next |
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

### Week 7 — Python Bridge for RDF (Smart Buildings)  
*Only structures needed later: identity, nesting, uniqueness, tiny “graphs”*

- **Day 41 — Buildings as Graphs, Not Only Tables:** Rows vs relationships; why BAS interoperability uses graphs.
- **Day 42 — URIs & IRIs as Identity:** Strings that name things globally; cool URI vs literal.
- **Day 43 — Prefix Maps:** `dict` from prefix string to base IRI; expand `brick:AHU` by hand.
- **Day 44 — Triples as Data:** `(subject, predicate, object)` tuples; `list` of triples as a toy graph.
- **Day 45 — Literals vs Resources:** When the object is a typed value (lexical + datatype name as strings).
- **Day 46 — Adjacency-Style `dict`:** `subject -> list` of `(predicate, object)` pairs (simple directed multigraph).
- **Day 47 — From Rows to Nodes:** Nested `dict` records for one equipment + points (bridge from CSV/BACnet thinking).

---

### Week 8 — RDF & Turtle (Theory + `rdflib`)  
*Triple model, syntax, loading graphs in Python*

- **Day 48 — RDF Triple Model:** Subject, predicate, object; blank nodes mentioned lightly.
- **Day 49 — `rdf:type` & Taxonomy:** Instance of a class; `rdfs:subClassOf` as “is-a” chain (concept + tiny triples).
- **Day 50 — Properties:** `rdf:Property`; domain and range (read diagrams / docs, not proofs).
- **Day 51 — Reading Turtle:** `.` `;` `,` blocks; prefixes; comments.
- **Day 52 — `rdflib` Graph from Turtle:** Parse a string; count triples; iterate `graph.triples(...)`.
- **Day 53 — Serialization:** `graph.serialize(format="turtle")`; round-trip sanity check.
- **Day 54 — Merging Graphs:** Add triples from two sources; dedupe with a `set` of frozen rows (pattern only).

---

### Week 9 — Brick Ontology on RDF  
*Classes and relationships for equipment and points*

- **Day 55 — `brick:` Namespace:** What Brick adds on top of RDF/RDFS.
- **Day 56 — Equipment Taxonomy:** AHU, VAV, chiller as classes; subclass chains at high level.
- **Day 57 — Key Predicates:** `brick:hasPoint`, `brick:isPartOf`, `brick:feeds` (meanings, not every term).
- **Day 58 — Hand-Author a Tiny Model:** Write Turtle for one AHU + one SAT sensor (by hand, then optional parse check).
- **Day 59 — Haystack Tags vs Brick Graphs:** When tags are enough vs when you need a mergeable RDF model.
- **Day 60 — FDD & Ontology:** How rule `inputs` (e.g. open-fdd) map to Brick-class *names* as logical columns (conceptual).

---

### Week 10 — SPARQL for Brick Graphs  
*Patterns, filters, optional data, capstone query*

- **Day 61 — Why SPARQL:** Graph pattern matching; WHERE block as “shape to find.”
- **Day 62 — `SELECT` & Basic `WHERE`:** Variables `?x`; one- and two-triple patterns on `rdflib` data.
- **Day 63 — `FILTER` & `BIND`:** Numeric comparisons; computed columns in result rows.
- **Day 64 — `OPTIONAL`:** Points that may be missing; null-like unbound variables.
- **Day 65 — `UNION`:** Alternative patterns (this OR that equipment layout).
- **Day 66 — `ASK`:** Existence checks for commissioning rules (“is there any…?”).
- **Day 67 — `DISTINCT`, `ORDER BY`, `LIMIT`:** Practical query hygiene on building models.
- **Day 68 — Capstone:** Multi-clause `SELECT` on a small Brick TTL file bundled with the lesson; document what you queried.

---


## License

MIT License — use, remix, share forward. Built for the BAS community.
