# Py BACnet Stacks Playground

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white)](https://discord.gg/Ta48yQF8fC)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/bbartling/py-bacnet-stacks-playground)](LICENSE)
[![DIY BACnet router](https://img.shields.io/badge/active-vibe__code__apps__13-009966)](vibe_code_apps_13/)
[![Rust BACnet lab](https://img.shields.io/badge/active-vibe__code__apps__16-009966)](vibe_code_apps_16/)
[![Residential DSM lab](https://img.shields.io/badge/active-vibe__code__apps__23-2ea44f)](vibe_code_apps_23/)
[![GHCR vibe19](https://img.shields.io/badge/GHCR-vibe19-blue?logo=docker&logoColor=white)](https://github.com/bbartling/py-bacnet-stacks-playground/pkgs/container/vibe19)
[![EnergyPlus MCP](https://img.shields.io/badge/EnergyPlus-MCP%2026.1-blue?logo=docker&logoColor=white)](vibe_code_apps_20/third_party/README.md)
[![Docs PDF](https://img.shields.io/badge/docs-PDF%20manual-blue)](vibe_code_apps_12/pdf/vibe12-edge-fdd-guide.pdf)
[![AWS IoT Core](https://img.shields.io/badge/cloud-AWS%20IoT%20Core-FF9900?logo=amazonaws&logoColor=white)](vibe_code_apps_12/aws_cloud_pipeline/)
[![LFCS 50-day](https://img.shields.io/badge/LFCS-50%20day%20Pi%20labs-FCC624?logo=linux&logoColor=black)](lessons/lfcs/)

## **Applied Python + BACnet → Dual-Language Networking + Edge Automation for HVAC Controls Technicians, IoT Practitioners, and Building-Systems Tinkerers**

Welcome to the **Py BACnet Stacks Playground** — a hands-on, applied repository where **every Day 1–75 lesson is dual-language**: same scaffold (`Goal` → `Key Takeaway`), then a companion so you can do the day’s idea in **Python and Rust**. Days **1–27** lead with **Python + BACnet** (BAC0 / BACpypes3) and a **Rust companion**. After Day 27 the **main text flips to Rust** (Cargo, sockets, tcpdump/Wireshark, **[rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)**, **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)**), with a matching **Python companion** each day—not a Python drop-off. Semantic weeks use **RDF dual-stack `rdflib` / `oxrdf`** (Brick / Haystack / 223P mindset, shared Turtle and SPARQL intent).

The early *vibe code* apps stay grounded in **Python, BAC0, and BACpypes3**, where you build practical tools by directly interacting with BACnet devices—reading values, writing commands, inspecting priority arrays, and understanding real control behavior in the field.

From **Day 28** onward, each mini-challenge still pairs both languages: **Rust-main** covers Cargo, types and collections, **socket I/O**, **packet capture labs** with per-day Wireshark display filters, and production-style **BACnet / Haystack clients**; the **Python companion** mirrors the same lab intent (e.g. `socket` / BAC0 / `requests`, and later **`rdflib` SPARQL** next to **`oxrdf`**). The **semantic modeling capstone** is graphs, Turtle, and query patterns on **both** stacks—not Rust-only.

The goal is to experiment with lightweight agents, platform services, and supervisory logic running continuously on a Raspberry Pi or edge gateway (e.g. **open-fdd**), bringing scripts closer to real-world building automation deployments—with **pcap evidence** when the wire disagrees with your driver.

Come join the journey as we play around with Python, **Rust**, AI, BACnet, Haystack, Wireshark, and computer science theory in a fun, hands-on playground designed for learning. This series is geared toward people with little to no technical background beyond real-world field experience as building automation technicians.

---

## Who This Is For

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet from the field and wants to code it in **Python and Rust**, play with **Wireshark**, and learn graph modeling (`rdflib` / `oxrdf`) with AI-assisted workflows

### Learning paths

| Track | What you get | Start here |
| --- | --- | --- |
| **Python + Rust (BACnet / networking / RDF)** | Days **1–75 dual-language**: shared scaffold every day; **1–27** Python-main + Rust companion; **28–75** Rust-main + Python companion (same lab intent); RDF weeks **`rdflib` + `oxrdf`** with shared Turtle/SPARQL | [Computer Science Theory 101](#computer-science-theory-101-weekly-outline) · [`lessons/`](lessons/) · [`lessons/INDEX.md`](lessons/INDEX.md) · Day 1: [`lessons/day01.md`](lessons/day01.md) |
| **Linux LFCS (Raspberry Pi)** | 50-day crash course for the Linux Foundation Certified System Administrator exam | [LFCS 50-day crash course](#lfcs-50-day-crash-course) · [`lessons/lfcs/`](lessons/lfcs/) · [`lessons/lfcs/INDEX.md`](lessons/lfcs/INDEX.md) · Day 1: [`lessons/lfcs/day01.md`](lessons/lfcs/day01.md) |
| **DIY BACnet router (app 13)** | Pi/Linux **BACnet/IP ↔ MS/TP** router; three-phase Rust lab (RS-485 wire test → MS/TP mini-device → router appliance) | [`vibe_code_apps_13/`](vibe_code_apps_13/) · [AGENTS.md](vibe_code_apps_13/AGENTS.md) |
| **Open FDD Vibe Coder (app 19)** | Streamlit + pandas 50-rule cookbook lab *(completed reference)* | [`vibe_code_apps_19/`](vibe_code_apps_19/) · [AGENTS.md](vibe_code_apps_19/AGENTS.md) |
| **OpenFDD WattLab (app 20)** | EnergyPlus ECM screens *(completed reference)* | [`vibe_code_apps_20/`](vibe_code_apps_20/) · [README](vibe_code_apps_20/README.md) |
| **Demand twin (app 21)** | Liberty cooling DR twin *(completed reference)* | [`vibe_code_apps_21/`](vibe_code_apps_21/) · [AGENTS.md](vibe_code_apps_21/AGENTS.md) |
| **Lakeside ES (app 22)** | Lakeside heating DSM / grid-search stack *(completed reference)* | [`vibe_code_apps_22/`](vibe_code_apps_22/) · [AGENTS.md](vibe_code_apps_22/AGENTS.md) |
| **Residential DSM lab (app 23)** | Heat-pump home DR + thermostat/battery grid search | [`vibe_code_apps_23/`](vibe_code_apps_23/) · [README](vibe_code_apps_23/README.md) |

---


## Vibe Code Checkpoints

Hands-on milestones from BACnet scripting to cloud FDD. **Featured builds** are linked below; checkpoints **1–10** are historical demos.

| # | Checkpoint | Summary | Status |
| --- | --- | --- | --- |
| **1** | **[BAC0 + bacpypes3 basics](vibe_code_apps_1/)** | Read/write `present-value`, release with `NULL`, priority arrays. | Done |
| **2** | **[RPM apps](vibe_code_apps_2/)** | `ReadPropertyMultiple` across devices; CSV logs with daily rotation. | Done |
| **3** | **[Priority array tools](vibe_code_apps_3/)** | Parse `priority-array`, inspect overrides, control authority. | Done |
| **4** | **[BACnet server apps](vibe_code_apps_4/)** | Mini BACnet device: schedules, calendars, weather server inputs. | Done |
| **5** | **[Device discovery tools](vibe_code_apps_5/)** | `Who-Is` / `I-Am` scanning and device enumeration. | Done |
| **6** | **[VOLTTRON + OpenClaw exploration](vibe_code_apps_6/)** | VOLTTRON deploy experiments; AI-assisted edge BAS/FDD scaffolding. | Done |
| **7** | **[VOLTTRON v9 BAS-style web agent](vibe_code_apps_7/)** | BACnet-integrated supervisory web agent on VOLTTRON v9. | Done |
| **8** | **[BAS schedule widget demo](vibe_code_apps_8/)** | Schedule widget and frontend UI concepts. | Done |
| **9** | **[diy-bas — beginning phase](vibe_code_apps_9/)** | First `diy-bas` shell: **Flask** API + vanilla JS UI. | Done |
| **10** | **[diy-bas — integration](vibe_code_apps_10/)** | Auth, alarms, schedules, trends, discovery in **Django + React** (superseded by **11**). | Done |
| **11** | **[Agentic BAS from spec](vibe_code_apps_11/)** | Spec-driven BAS via **SKILL.md**, workspace memory, and cron-driven **Codex CLI** agent (drivers, commissioning, web app). | Paused |
| **12** | **[AI-assisted edge-to-cloud HVAC FDD](vibe_code_apps_12/)** | End-to-end HVAC fault detection pipeline: BACnet discovery, commissioning CSVs, RPM polling, AWS IoT Core MQTT, DynamoDB historian, Lambda dashboard, Python FDD Rule Lab, Brick-style data modeling, and AI-assisted development workflows. | Done |
| **13** | **[DIY BACnet router](vibe_code_apps_13/)** | Pi/Linux **BACnet/IP ↔ MS/TP** router in Rust (`rusty-bacnet`): Phase 1 RS-485 wire test → Phase 2 MS/TP mini-device → Phase 3 router appliance. Informed by app **14**. | **Active** |
| **14** | **[BACnet routing research lab](vibe_code_apps_14/)** | BACpypes3 timed labs (dual [mini-device](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py), [ipv4 router](https://github.com/JoelBender/BACpypes3/blob/main/samples/ipv4-to-ipv4.py), pcaps) toward [Misty3](https://github.com/raghavan97/misty3) and [router-mstp](https://github.com/bacnet-stack/bacnet-stack/tree/master/apps/router-mstp). | **Active** |
| **15** | **[Rust embedded BACnet device](vibe_code_apps_15/)** | Embedded **Rust** BACnet on **STM32 NUCLEO-F401RE**; **RS-485** / MS/TP lab — [DigiKey NUCLEO-F401RE](https://www.digikey.com/en/products/detail/stmicroelectronics/NUCLEO-F401RE/4695525). | **Active** |
| **16** | **[Rust BACnet stack lab](vibe_code_apps_16/)** | [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) server + probe; [Open-FDD mimic](./vibe_code_apps_16/openfdd-bacnet-mimic/) (device 599999); [BACnet → Feather concept](./vibe_code_apps_16/openfdd-bacnet-feather-concept/) (mini-device + poller + atomic Feather + tailer). | **Active** |
| **17** | **[Project Haystack playground](vibe_code_apps_17/)** | Niagara **nHaystack** Pi lab, [`rusty-haystack`](https://github.com/jscott3201/rusty-haystack) (Rust client/server + PyO3), and [`pyhaystack`](https://github.com/ChristianTremblay/pyhaystack) (Python). | **Active** |
| **18** | **[DIY BAS / Haystack data lake (Rust)](vibe_code_apps_18/)** · [Discussion #5](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5) | Read-only **`bas-haystack-lake-rs`**: Haystack collector, Postgres lake, admin API, sanitized Open-FDD JSON API, alerts, Docker/CI — agent prompt in [AGENTS.md](vibe_code_apps_18/AGENTS.md). | **Active** |
| **19** | **[Open FDD Vibe Coder (Streamlit)](vibe_code_apps_19/)** · [AGENTS.md](vibe_code_apps_19/AGENTS.md) | Streamlit + pandas twin of the [Open-FDD Pandas Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) (50 rules): zip packages, role mapping, Plots / RCx, agent CLI, session restore. Container: `ghcr.io/bbartling/vibe19`. | Done |
| **20** | **[OpenFDD WattLab](vibe_code_apps_20/)** · [AGENTS.md](vibe_code_apps_20/AGENTS.md) | EnergyPlus companion to vibe19: approved MeasureBriefs → Docker `energyplus-mcp-dev` (EP 26.1) easy button → progressive schedule / GL36-proxy IDF patches → `result_record` QA. | Done |
| **21** | **[Demand-management twin](vibe_code_apps_21/)** · [AGENTS.md](vibe_code_apps_21/AGENTS.md) | Liberty Building cooling DR: G14 Twin → hourly E+ farm → sklearn `facility_kw` → Flask / Unity scrubbers (HE 14–16). | Done |
| **22** | **[Lakeside ES (unified)](vibe_code_apps_22/)** · [AGENTS.md](vibe_code_apps_22/AGENTS.md) | Lakeside Elementary (southern WI): ALC→openfdd, IdealLoads G14 (interval + utility bills), heating DSM ML (HE 05–09), OpenStudio OSM; `LAKESIDE_SITE_ROOT` for site data. | Done |
| **23** | **[Residential heat-pump DSM](vibe_code_apps_23/)** · [README](vibe_code_apps_23/README.md) | Hypothetical heat-pump home at 5-min resolution: DR demo, illustrative TOU thermostat grid, battery co-optimization, compute telemetry. Grid-search lessons preserved. | **Active** |



---

## Computer Science Theory 101 Weekly Outline

These are AI-generated mini lessons designed as daily challenges with a **shared scaffold** on every day (`Goal` → `Key Takeaway`, then a language companion). **Every day is Python and Rust**—only which side is “main” flips:

| Days | Main text | Companion (same-day, parallel intent) |
| --- | --- | --- |
| **1–27** | Python + BACnet | **Rust companion** |
| **28–75** | Rust (Cargo → sockets → rusty-bacnet → rusty-haystack → RDF) | **Python companion** |
| **55–75 RDF** | `oxrdf` (Rust) | `rdflib` + SPARQL (Python); shared Turtle / query intent |

Daily labs include **tcpdump** / **Wireshark** — see [`lessons/lab-scripts/`](lessons/lab-scripts/). Capstone starters: [`lessons/capstone/`](lessons/capstone/).

**Track tip:** On Day 1, install Python *and* Rust (`rustup`); keep `~/rust-lab` and `~/py-lab`. Do **both** the main lesson and the companion the same day.


### Week 1 — Fundamentals & First BACnet App  
*Part I: Variables, operators, strings, numbers, booleans, input/output, lists · + Rust companions*

- **Day 1 — Installing Python & Pip (BACnet Ready):** Set up Python, pip, BAC0, bacpypes3. **Rust:** install `rustup` / Cargo, `cargo new`, first `println!`.
- **Day 2 — Variables & Arithmetic:** Store values, arithmetic, operator precedence. **Rust:** `let` / `let mut`, `i32` / `f64`.
- **Day 3 — Working with Strings:** Create, concatenate, index, slice strings. **Rust:** `String` vs `&str`.
- **Day 4 — Numbers, Booleans & Comparisons:** Numeric types, comparisons, truthiness. **Rust:** `bool`, comparisons.
- **Day 5 — User Input & Output:** `input()`, type conversion, f-strings. **Rust:** `println!`, `read_line`, `parse`.
- **Day 6 — Introducing Lists:** Create, index, slice, append, `len()`. **Rust:** `Vec<T>`.
- **Day 7 — List Operations & Methods:** append, extend, insert, remove, sort, copy. **Rust:** `Vec` methods, `clone`.

---

### Week 2 — Control Structures & Data Collection  
*Part II: Loops, conditionals, functions, files · + Rust companions*

- **Day 8 — For Loops & Range:** Iterate over lists/strings/ranges, `enumerate()`. **Rust:** `for`, `0..n`, `.enumerate()`.
- **Day 9 — Conditionals & While Loops:** `if`/`elif`/`else`, `while`, sentinel loops. **Rust:** `if` expressions, `while`.
- **Day 10 — String Methods: Split, Join & Case:** `split()`, `join()`, case conversion. **Rust:** `.split`, `.collect`, `.to_uppercase()`.
- **Day 11 — Introducing Dictionaries:** Keys, values, add, retrieve, membership. **Rust:** `HashMap`, `.get` → `Option`.
- **Day 12 — Looping over Dictionaries:** `items()`, `keys()`, `values()` (no comprehensions). **Rust:** `for (k, v) in &map`.
- **Day 13 — Tuples & Sets (Light):** Immutable tuples, sets for membership (optional). **Rust:** tuples, arrays.
- **Day 14 — Loops & Sentinels:** `break`, `continue`, common loop patterns. **Rust:** same keywords.

---

### Week 3 — Functions, Modules & Files  
*Part II continued: Reusable code, modules, file I/O · + Rust companions*

- **Day 15 — Writing Functions:** Define functions, parameters, return, docstrings. **Rust:** `fn`, typed params/returns.
- **Day 16 — Modules & the Standard Library:** `math`, `random`, organising code. **Rust:** `use std::...`, crates.
- **Day 17 — Reading & Writing Files:** `open()`, `with`, read/write text and CSV. **Rust:** `std::fs`.
- **Day 18 — Handling Errors:** `try`/`except`, robust programs. **Rust:** `Result`, `Option` preview.
- **Day 19 — Week 3 Review:** CSV of sensor readings, statistics, error handling. **Rust:** small review project.
- **Day 20 — Built-in Functions:** `min()`, `max()`, `sorted()`, `sum()`, `zip()` (no comprehensions). **Rust:** iterators.
- **Day 21 — Slicing & String Formatting:** Advanced f-strings, slicing. **Rust:** `format!`, slices.

---

### Week 4 — Data Structures & Discovery  
*Part III: Lists, dicts, file I/O · + Rust companions*

- **Day 22 — Working with Nested Data:** Lists of dicts, dicts of lists (loops only, no comprehensions). **Rust:** `Vec` of `struct`.
- **Day 23 — Random & Math:** `random`, `math` for simulations. **Rust:** `rand` crate.
- **Day 24 — any(), all() & Simple Patterns:** Boolean checks on collections. **Rust:** `.any` / `.all`.
- **Day 25 — Documentation & help():** Docstrings, comments, `help()`. **Rust:** `///`, `cargo doc`.
- **Day 26 — Week 4 Review:** Nested data, built-ins, loops. **Rust:** map + alarm review.

---

### Week 5 — Rust Fast Track (After Python Day 27)  
*Rust-main + Python companion each day — ownership, types, control flow, collections*

- **Day 27 — What Is an Algorithm? (HVAC & data):** Finite steps, inputs/outputs; **Rust:** ownership teaser (move vs `&`).
- **Day 28 — Rust recap & ownership crash course:** Confirm Cargo; **ownership, borrowing, lifetimes** intuition (install was Day 1). **Python:** GC vs ownership companion.
- **Day 29 — Types, Operators & Variables:** Scalars, `mut`, formatting BACnet-style readings. **Python:** same readings with types/`f`-strings.
- **Day 30 — Control Flow:** `if`, loops, `match` for alarm/priority-style logic. **Python:** `if` / `match`/`case`.
- **Day 31 — Functions, Option & Result:** Error handling before sockets. **Python:** functions + exceptions / `Optional`.
- **Day 32 — struct, enum & impl:** Model BACnet points and object kinds. **Python:** dataclasses / Enum.
- **Day 33 — Vec, HashMap & String:** Device caches and tag maps. **Python:** list / dict.
- **Day 34 — Ownership & Borrowing (practice):** References for network buffers and APIs (builds on Day 28). **Python:** aliases / mutability companion.

---

### Week 5b — Network Programming & Wireshark  
*UDP/TCP, tcpdump pcaps, display filters — Rust-main; Python companion mirrors sockets / capture workflow*

- **Day 35 — Network map:** BACnet UDP `:47808`, Haystack TCP `:443`, Modbus TCP—bench topology.
- **Day 36 — UDP sockets in Rust:** Echo lab; BACnet datagram mindset. **Python:** `socket` UDP echo.
- **Day 36b — Modbus TCP (beginner OT):** Register read over TCP `:502`/`:1502`—easier than BACnet; Wireshark `modbus` filter. **Python:** pymodbus / raw TCP sketch.
- **Day 37 — TCP client/server:** Echo lab; HTTP/TLS foundation. **Python:** `socket` TCP.
- **Day 38 — tcpdump & PCAP workflow:** `capture_pcap.sh`, snaplen, offline analysis.
- **Day 39 — Wireshark: BACnet on UDP:** BVLC/NPDU/APDU; filter `udp.port == 47808`.
- **Day 40 — Wireshark: TCP, TLS & HTTP:** Haystack preview; filter `tcp.port == 443`.

---

### Week 6 — rusty-bacnet Specialty  
*Discovery, ReadProperty, RPM, writes (lab-safe), capstone CLI — Rust-main; Python companion via BAC0 / bacpypes3*

- **Day 41 — Intro rusty-bacnet:** Clone, build, map Who-Is/ReadProperty APIs.
- **Day 42 — ReadProperty:** Device **5007** bench read in Rust.
- **Day 43 — ReadPropertyMultiple:** Poll loops and traffic math.
- **Day 44 — WriteProperty & priority:** Lab/sim only; read-back discipline.
- **Day 45 — Who-Is / I-Am scan:** Discovery table in `HashMap`.
- **Day 46 — BACnet capstone:** Mini commission CLI + CSV snapshot.
- **Day 47 — Async preview (tokio):** Why edge services use async I/O. **Python:** `asyncio` sketch.

---

### Week 6b — rusty-haystack & HTTP Haystack Ops  
*Niagara nHaystack, Basic vs SCRAM, fixtures, tag↔BACnet mapping — Rust-main; Python companion via requests/httpx*

- **Day 48 — HTTP mental model:** `/about`, `/read`, `/ops`; status codes.
- **Day 49 — rusty-haystack setup:** Build client; Niagara URL and TLS lab notes.
- **Day 50 — /read & Zinc filters:** Point reads and grid parsing.
- **Day 51 — Auth: Basic vs SCRAM:** Niagara `HTTPBasicScheme` vs Project Haystack SCRAM.
- **Day 52 — Golden fixtures:** Offline dev with captured Zinc/HTTP fixtures.
- **Day 53 — Correlate Haystack tags with BACnet points:** Mapping CSV/structs.
- **Day 54 — Haystack capstone:** `niagara-read` CLI with clap flags.

---

### Week 7 — RDF Bridge (rdflib + oxrdf)  
*Triples, IRIs, Turtle, graphs — dual-stack*

- **Day 55 — Why RDF after protocols:** Triples; same sample on both stacks.
- **Day 56 — URIs & prefix maps:** QName expansion; shared prefixes.
- **Day 57 — Triples & literals:** IRI vs typed literal.
- **Day 58 — Reading Turtle:** Hand syntax; `oxrdf` / `rdflib` load.
- **Day 59 — Adjacency-list graph:** Subject → edges; parallel `rdflib` Graph.
- **Day 60 — rdf:type & Brick taxonomy:** Class and subclass chains.
- **Day 61 — Haystack tags vs Brick graphs:** When tags vs mergeable RDF.

---

### Week 8 — Brick Models & Query Patterns (rdflib + oxrdf)  
*Hand-authored TTL; SPARQL intent on both stacks*

- **Day 62 — Hand-author Brick AHU model:** `ahu1.ttl` capstone piece.
- **Day 63 — Pattern matching queries:** Tiny `SELECT`-style patterns.
- **Day 64 — Multi-protocol PCAP challenge:** One file, three Wireshark filters.
- **Day 65 — open-fdd drivers & semantic layer:** Transport → driver → RDF.
- **Day 66 — Serialize graph to Turtle:** Round-trip with `oxrdf` / `rdflib`.
- **Day 67 — ASHRAE 223P alignment (concept):** Brick, Haystack, 223P roles.

---

### Week 9 — Live Data → Graph & Agent-Ready Export  
*BACnet → RDF; SPARQL FILTER/ASK; JSON for tools*

- **Day 68 — BACnet read → RDF triples:** Live snapshot into graph.
- **Day 69 — FILTER & OPTIONAL patterns:** Same SPARQL on both stacks.
- **Day 70 — UNION & ASK queries:** Existence checks for commissioning.
- **Day 71 — DISTINCT, ORDER BY, LIMIT:** Practical query hygiene.
- **Day 72 — Haystack → RDF export path:** Zinc rows to triples stub.
- **Day 73 — Agent-ready metadata:** JSON/NDJSON point rows for MCP/agents.

---

### Week 10 — Course Synthesis & Final Capstone  
*Portfolio: dual-language CLIs + TTL + pcaps + `rdflib` SPARQL / `oxrdf` graph-export*

- **Day 74 — Course review:** Python → Rust → Wireshark → dual-stack graph doc.
- **Day 75 — Final capstone:** Multi-protocol semantic snapshot; `oxrdf` in `graph-export`; `rdflib` SPARQL on `ahu1.ttl`; Wireshark filters in `pcaps/README.md`.

---

## LFCS 50-day crash course

**Pass the [Linux Foundation Certified System Administrator (LFCS)](https://training.linuxfoundation.org/certification/linux-foundation-certified-sysadmin-lfcs/)** with daily mini-labs on a **Raspberry Pi** (or any Linux VM) — same short format as the BACnet/Rust lessons (`Goal` · `Concept` · `Micro exercises` · `Key takeaway`).

| Item | Link |
| --- | --- |
| **Start here** | [`lessons/lfcs/INDEX.md`](lessons/lfcs/INDEX.md) |
| **Day 1** | [`lessons/lfcs/day01.md`](lessons/lfcs/day01.md) |
| **Format twin** | Same style as [`lessons/day31.md`](lessons/day31.md) |

```text
git clone <this-repo>
cd py-bacnet-stacks-playground/lessons/lfcs
# open day01.md → run commands on the Pi → micro exercises → next day
```

**~20–40 minutes/day.** Snapshot your SD card or VM before storage/network experiments.

### Domain map (exam weights)

| Week | Days | Domain | Weight |
| --- | --- | --- | --- |
| 1–2 | 1–13 | **Essential Commands** — shell, files, git, systemd, perf, disk, SSL | 20% |
| 3 | 14–19 | **Users and Groups** — accounts, profiles, limits, ACLs, LDAP client | 10% |
| 4 | 20–28 | **Operations Deployment** — sysctl, cron, packages, recovery, libvirt, containers, SELinux | 25% |
| 5 | 29–37 | **Networking** — IP, time, SSH, firewall/NAT, routes, bridge/bond, reverse proxy | 25% |
| 6 | 38–45 | **Storage** — LVM, VFS, filesystems, NFS/iSCSI, swap, autofs, I/O | 20% |
| 7 | 46–50 | **Exam practice** — mixed mocks, weak-area drills, strategy, final checklist | — |

### Weekly outline

#### Week 1 — Essential Commands foundation
- **Day 1** — Lab setup & LFCS map (Pi snapshot, domain weights)
- **Day 2** — Shell, paths & man pages
- **Day 3** — Files, find & locate
- **Day 4** — Permissions & ownership
- **Day 5** — Text tools: grep, head, cut
- **Day 6** — Pipes, redirection & tee
- **Day 7** — Basic Git operations

#### Week 2 — Services, logs & certs
- **Day 8** — systemd services
- **Day 9** — Monitor performance
- **Day 10** — Logs & service constraints
- **Day 11** — Troubleshoot disk space
- **Day 12** — SSL certificates
- **Day 13** — Essential Commands review

#### Week 3 — Users and Groups
- **Day 14** — Users & groups
- **Day 15** — Environment profiles
- **Day 16** — User resource limits
- **Day 17** — ACLs
- **Day 18** — LDAP client accounts
- **Day 19** — Users & Groups review

#### Week 4 — Operations Deployment
- **Day 20** — Kernel parameters (sysctl)
- **Day 21** — Processes & services
- **Day 22** — Schedule jobs (cron / timers)
- **Day 23** — Packages & repositories
- **Day 24** — Recover from failures
- **Day 25** — Virtual machines (libvirt)
- **Day 26** — Containers (podman/docker)
- **Day 27** — SELinux basics (AppArmor note for Pi OS)
- **Day 28** — Operations review

#### Week 5 — Networking
- **Day 29** — IPv4/IPv6 & hostname
- **Day 30** — Time sync
- **Day 31** — Troubleshoot networking
- **Day 32** — OpenSSH server & client
- **Day 33** — Firewall, NAT & redirect
- **Day 34** — Static routing
- **Day 35** — Bridge & bonding
- **Day 36** — Reverse proxy & load balancer
- **Day 37** — Networking review

#### Week 6 — Storage
- **Day 38** — LVM (loop-file safe on Pi)
- **Day 39** — Virtual filesystem (`/proc`, `/sys`)
- **Day 40** — Filesystems create & repair
- **Day 41** — Remote FS & network block (NFS / iSCSI)
- **Day 42** — Swap space
- **Day 43** — Automounters (autofs)
- **Day 44** — Storage performance
- **Day 45** — Storage review

#### Week 7 — Exam practice
- **Day 46** — Mixed practice A
- **Day 47** — Mixed practice B
- **Day 48** — Weak-area drills
- **Day 49** — Exam strategy
- **Day 50** — Final mock & checklist

Pi OS notes are included where the exam expects **SELinux/libvirt** but the Pi runs **AppArmor** or lacks a hypervisor — you still learn the commands for exam day.

---

## License

MIT License — use, remix, share forward. Built for the BAS community ❤️🥰.
