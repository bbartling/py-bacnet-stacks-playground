# Py BACnet Stacks Playground

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white)](https://discord.gg/Ta48yQF8fC)



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

| #      | Checkpoint                                                                                   | Build Goal                                                                                                                                                                                                                                          | Status      |
| ------ | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| **1**  | **BAC0 + bacpypes3 basics**                                                                  | Read `present-value`, write points, release with `NULL`, and learn priority arrays.                                                                                                                                                                 | Done        |
| **2**  | **RPM apps**                                                                                 | Use `ReadPropertyMultiple` across devices, log to CSV, and rotate daily files.                                                                                                                                                                      | Done        |
| **3**  | **Priority array tools**                                                                     | Parse `priority-array`, inspect overrides, and understand control authority.                                                                                                                                                                        | Done        |
| **4**  | **BACnet server apps**                                                                       | Build a mini BACnet device with schedule/calendar objects and weather server inputs.                                                                                                                                                                | Done        |
| **5**  | **Device discovery tools**                                                                   | Implement `Who-Is` / `I-Am` scanning and device enumeration.                                                                                                                                                                                        | Done        |
| **6**  | **VOLTTRON deployment exploration with OpenClaw**                                            | Explore deploying VOLTTRON with OpenClaw support, test the environment setup, and investigate how AI-assisted workflows can help scaffold edge BAS/FDD applications.                                                                                | Done        |
| **7**  | **VOLTTRON v9 BAS-style web agent**                                                          | Build and test a VOLTTRON v9 web agent with BACnet integration, mimicking a lightweight BAS supervisory interface.                                                                                                                                  | Done        |
| **8**  | **BAS schedule widget demo**                                                                 | Build out a BAS-style schedule widget and frontend UI concepts.                                                                                                                                                                                     | Done        |
| **9**  | **diy-bas beginning phase**                                                                  | Create the first primitive version of the `diy-bas` application.                                                                                                                                                                                    | Done        |
| **10** | **diy-bas integration**                                                                      | Combine authentication, alarms, schedules, trends, and BACnet discovery.                                                                                                                                                                            | Done        |
| **11** | **diy-bas: Django production DB, unit tests, React front end, notifications, role services** | Move the supervisory app toward production: managed database, unit/integration tests for critical paths, React UI shell, outgoing notifications such as ntfy for alerts, and clearer user/role services for auth, RBAC, and integration boundaries. | **Current** |
| **12** | **diy-bas hardening**                                                                        | Add persistence depth, audit logging polish, security cleanup, and deploy/ops workflows beyond the initial integration.                                                                                                                             | Next        |
| **13** | **diy-bas final app release**                                                                | Ship the Raspberry Pi-ready supervisory BAS application.                                                                                                                                                                                            | Planned     |
| **14** | **Rust BACnet stack**                                                                        | Bonus: integrate [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) with Python bindings.                                                                                                                                                 | TODO        |
| **15** | **Protocol debugging**                                                                       | Bonus: use Wireshark and Linux tools to validate BACnet/IP behavior.                                                                                                                                                                                | TODO        |


---

## Computer Science Theory 101 Weekly Outline

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

### Optional — Grid & maze hobby (Lua reference: maze-algorithm-sandbox)  
*Optional CS play after the HVAC algorithms arc; skip straight to Week 7 if you prefer*

- **Day 41 — Grids & Neighbors:** 2D nested lists, four-connected neighbors, `visited` flags.
- **Day 42 — Stacks & DFS:** `list` as LIFO; depth-first walk on a tiny character maze.
- **Day 43 — Maze generation:** Iterative recursive-backtracking carve (stack, random neighbor), Python counterpart to the Lua **MazeGenerator** pattern.

---

### Week 7 — Python Bridge for RDF (Smart Buildings)  
*Only structures needed later: identity, nesting, uniqueness, tiny “graphs”*

- **Day 44 — Buildings as Graphs, Not Only Tables:** Rows vs relationships; why BAS interoperability uses graphs.
- **Day 45 — URIs & IRIs as Identity:** Strings that name things globally; cool URI vs literal.
- **Day 46 — Prefix Maps:** `dict` from prefix string to base IRI; expand `brick:AHU` by hand.
- **Day 47 — Triples as Data:** `(subject, predicate, object)` tuples; `list` of triples as a toy graph.
- **Day 48 — Literals vs Resources:** When the object is a typed value (lexical + datatype name as strings).
- **Day 49 — Adjacency-Style `dict`:** `subject -> list` of `(predicate, object)` pairs (simple directed multigraph).
- **Day 50 — From Rows to Nodes:** Nested `dict` records for one equipment + points (bridge from CSV/BACnet thinking).

---

### Week 8 — RDF & Turtle (Theory + `rdflib`)  
*Triple model, syntax, loading graphs in Python*

- **Day 51 — RDF Triple Model:** Subject, predicate, object; blank nodes mentioned lightly.
- **Day 52 — `rdf:type` & Taxonomy:** Instance of a class; `rdfs:subClassOf` as “is-a” chain (concept + tiny triples).
- **Day 53 — Properties:** `rdf:Property`; domain and range (read diagrams / docs, not proofs).
- **Day 54 — Reading Turtle:** `.` `;` `,` blocks; prefixes; comments.
- **Day 55 — `rdflib` Graph from Turtle:** Parse a string; count triples; iterate `graph.triples(...)`.
- **Day 56 — Serialization:** `graph.serialize(format="turtle")`; round-trip sanity check.
- **Day 57 — Merging Graphs:** Add triples from two sources; dedupe with a `set` of frozen rows (pattern only).

---

### Week 9 — Brick Ontology on RDF  
*Classes and relationships for equipment and points*

- **Day 58 — `brick:` Namespace:** What Brick adds on top of RDF/RDFS.
- **Day 59 — Equipment Taxonomy:** AHU, VAV, chiller as classes; subclass chains at high level.
- **Day 60 — Key Predicates:** `brick:hasPoint`, `brick:isPartOf`, `brick:feeds` (meanings, not every term).
- **Day 61 — Hand-Author a Tiny Model:** Write Turtle for one AHU + one SAT sensor (by hand, then optional parse check).
- **Day 62 — Haystack Tags vs Brick Graphs:** When tags are enough vs when you need a mergeable RDF model.
- **Day 63 — FDD & Ontology:** How rule `inputs` (e.g. open-fdd) map to Brick-class *names* as logical columns (conceptual).

---

### Week 10 — SPARQL for Brick Graphs  
*Patterns, filters, optional data, capstone query*

- **Day 64 — Why SPARQL:** Graph pattern matching; WHERE block as “shape to find.”
- **Day 65 — `SELECT` & Basic `WHERE`:** Variables `?x`; one- and two-triple patterns on `rdflib` data.
- **Day 66 — `FILTER` & `BIND`:** Numeric comparisons; computed columns in result rows.
- **Day 67 — `OPTIONAL`:** Points that may be missing; null-like unbound variables.
- **Day 68 — `UNION`:** Alternative patterns (this OR that equipment layout).
- **Day 69 — `ASK`:** Existence checks for commissioning rules (“is there any…?”).
- **Day 70 — `DISTINCT`, `ORDER BY`, `LIMIT`:** Practical query hygiene on building models.
- **Day 71 — Capstone:** Multi-clause `SELECT` on a small Brick TTL file bundled with the lesson; document what you queried.

---


## License

MIT License — use, remix, share forward. Built for the BAS community.
