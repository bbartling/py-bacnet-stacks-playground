# Py BACnet Stacks Playground

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white)](https://discord.gg/Ta48yQF8fC)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/bbartling/py-bacnet-stacks-playground)](LICENSE)
[![BACnet edge + FDD](https://img.shields.io/badge/active-vibe__code__apps__12-009966)](vibe_code_apps_12/)
[![Rust BACnet lab](https://img.shields.io/badge/active-vibe__code__apps__16-009966)](vibe_code_apps_16/)
[![Docs PDF](https://img.shields.io/badge/docs-PDF%20manual-blue)](vibe_code_apps_12/pdf/vibe12-edge-fdd-guide.pdf)
[![AWS IoT Core](https://img.shields.io/badge/cloud-AWS%20IoT%20Core-FF9900?logo=amazonaws&logoColor=white)](vibe_code_apps_12/aws_cloud_pipeline/)
[![LFCS 50-day](https://img.shields.io/badge/LFCS-50%20day%20Pi%20labs-FCC624?logo=linux&logoColor=black)](lessons/lfcs/)

## **Applied Python + BACnet → Rust Networking + Edge Automation for HVAC Controls Technicians, IoT Practitioners, and Building-Systems Tinkerers**

Welcome to the **Py BACnet Stacks Playground** — a hands-on, applied repository that starts with **Python fundamentals and direct BACnet scripting**, then pivots after **Day 27** into a **fast-track Rust** path: **network programming** (UDP/TCP, tcpdump, Wireshark), **[rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)**, **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)**, and **RDF modeled in Rust** (Brick / Haystack / 223P mindset—not Python `rdflib`).

The early *vibe code* apps stay grounded in **Python, BAC0, and BACpypes3**, where you build practical tools by directly interacting with BACnet devices—reading values, writing commands, inspecting priority arrays, and understanding real control behavior in the field.

From **Day 28** onward, daily mini-challenges teach **Cargo**, Rust types and collections, **socket I/O**, **packet capture labs** with per-day Wireshark display filters, production-style **Rust BACnet and Haystack clients**, and a **semantic modeling capstone**—graphs, Turtle, and query patterns implemented with Rust data structures.

The goal is to experiment with lightweight agents, platform services, and supervisory logic running continuously on a Raspberry Pi or edge gateway (e.g. **open-fdd**), bringing scripts closer to real-world building automation deployments—with **pcap evidence** when the wire disagrees with your driver.

Come join the journey as we play around with Python, **Rust**, AI, BACnet, Haystack, Wireshark, and computer science theory in a fun, hands-on playground designed for learning. This series is geared toward people with little to no technical background beyond real-world field experience as building automation technicians.


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
| **11** | **[Agentic BAS from spec](vibe_code_apps_11/)** | **Paused.** Spec-driven BAS via **SKILL.md**, workspace memory, and cron-driven **Codex CLI** agent (drivers, commissioning, web app). | Paused |
| **12** | **[AI-assisted edge-to-cloud HVAC FDD](vibe_code_apps_12/)** | **Active featured build.** End-to-end HVAC fault detection pipeline: BACnet discovery, commissioning CSVs, RPM polling, AWS IoT Core MQTT, DynamoDB historian, Lambda dashboard, Python FDD Rule Lab, Brick-style data modeling, and AI-assisted development workflows. | **Active** |
| **13** | **[DIY BACnet router](vibe_code_apps_13/)** *(planned)* | Pi/Linux **BACnet/IP ↔ MS/TP** router using **bacnet-stack** `router-mstp`; informed by app **14**. | Planned |
| **14** | **[BACnet routing research lab](vibe_code_apps_14/)** | **Planned.** BACpypes3 timed labs (dual [mini-device](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py), [ipv4 router](https://github.com/JoelBender/BACpypes3/blob/main/samples/ipv4-to-ipv4.py), pcaps) toward [Misty3](https://github.com/raghavan97/misty3) and [router-mstp](https://github.com/bacnet-stack/bacnet-stack/tree/master/apps/router-mstp). | Planned |
| **15** | **[Rust embedded BACnet device](vibe_code_apps_15/)** *(planned)* | Embedded **Rust** BACnet on **STM32 NUCLEO-F401RE**; **RS-485** / MS/TP lab — [DigiKey NUCLEO-F401RE](https://www.digikey.com/en/products/detail/stmicroelectronics/NUCLEO-F401RE/4695525). | Planned |
| **16** | **[Rust BACnet stack lab](vibe_code_apps_16/)** | **Active featured build.** [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) server + probe; [Open-FDD mimic](./vibe_code_apps_16/openfdd-bacnet-mimic/) (device 599999); Python bindings + BACpypes3 benchmarks planned. | **Active** |
| **17** | **[Project Haystack playground](vibe_code_apps_17/)** | Niagara **nHaystack** Pi lab, [`rusty-haystack`](https://github.com/jscott3201/rusty-haystack) (Rust client/server + PyO3), and [`pyhaystack`](https://github.com/ChristianTremblay/pyhaystack) (Python). | **Active** |
| **18** | **[DIY BAS / Haystack data lake (Rust)](vibe_code_apps_18/)** · [Discussion #5](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5) | **Active featured build.** Read-only **`bas-haystack-lake-rs`**: Haystack collector, Postgres lake, admin API, sanitized Open-FDD JSON API, alerts, Docker/CI — agent prompt in [AGENTS.md](vibe_code_apps_18/AGENTS.md). | **Active** |



---

## Computer Science Theory 101 Weekly Outline

These are AI-generated mini lessons designed as daily challenges, starting at the complete beginner level with **Python + BACnet** (Days 1–27), then a **Rust fast track** through **network programming**, **rusty-bacnet**, **rusty-haystack**, and **RDF in Rust** (Days 28–75). Daily labs include **tcpdump capture scripts** and **Wireshark display filters**—see [`lessons/lab-scripts/`](lessons/lab-scripts/). Turn-key capstone starters: [`lessons/capstone/`](lessons/capstone/).


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

### Week 5 — Rust Fast Track (After Python Day 27)  
*Cargo, types, control flow, collections, ownership lite*

- **Day 27 — What Is an Algorithm? (HVAC & data):** Finite steps, inputs/outputs; **pivot note** to Rust track from Day 28.
- **Day 28 — Install Rust & Cargo:** `rustup`, `cargo new`, first binary on your edge PC.
- **Day 29 — Types, Operators & Variables:** Scalars, `mut`, formatting BACnet-style readings.
- **Day 30 — Control Flow:** `if`, loops, `match` for alarm/priority-style logic.
- **Day 31 — Functions, Option & Result:** Error handling before sockets.
- **Day 32 — struct, enum & impl:** Model BACnet points and object kinds.
- **Day 33 — Vec, HashMap & String:** Device caches and tag maps.
- **Day 34 — Ownership & Borrowing (fast track):** References for network buffers and APIs.

---

### Week 5b — Network Programming & Wireshark  
*UDP/TCP, tcpdump pcaps, display filters—typical coursework before application stacks*

- **Day 35 — Network map:** BACnet UDP `:47808`, Haystack TCP `:443`, Modbus TCP—bench topology.
- **Day 36 — UDP sockets in Rust:** Echo lab; BACnet datagram mindset.
- **Day 36b — Modbus TCP (beginner OT):** Register read over TCP `:502`/`:1502`—easier than BACnet; Wireshark `modbus` filter.
- **Day 37 — TCP client/server:** Echo lab; HTTP/TLS foundation.
- **Day 38 — tcpdump & PCAP workflow:** `capture_pcap.sh`, snaplen, offline analysis.
- **Day 39 — Wireshark: BACnet on UDP:** BVLC/NPDU/APDU; filter `udp.port == 47808`.
- **Day 40 — Wireshark: TCP, TLS & HTTP:** Haystack preview; filter `tcp.port == 443`.

---

### Week 6 — rusty-bacnet Specialty  
*Discovery, ReadProperty, RPM, writes (lab-safe), capstone CLI*

- **Day 41 — Intro rusty-bacnet:** Clone, build, map Who-Is/ReadProperty APIs.
- **Day 42 — ReadProperty:** Device **5007** bench read in Rust.
- **Day 43 — ReadPropertyMultiple:** Poll loops and traffic math.
- **Day 44 — WriteProperty & priority:** Lab/sim only; read-back discipline.
- **Day 45 — Who-Is / I-Am scan:** Discovery table in `HashMap`.
- **Day 46 — BACnet capstone:** Mini commission CLI + CSV snapshot.
- **Day 47 — Async preview (tokio):** Why edge services use async I/O.

---

### Week 6b — rusty-haystack & HTTP Haystack Ops  
*Niagara nHaystack, Basic vs SCRAM, fixtures, tag↔BACnet mapping*

- **Day 48 — HTTP mental model:** `/about`, `/read`, `/ops`; status codes.
- **Day 49 — rusty-haystack setup:** Build client; Niagara URL and TLS lab notes.
- **Day 50 — /read & Zinc filters:** Point reads and grid parsing.
- **Day 51 — Auth: Basic vs SCRAM:** Niagara `HTTPBasicScheme` vs Project Haystack SCRAM.
- **Day 52 — Golden fixtures:** Offline dev with captured Zinc/HTTP fixtures.
- **Day 53 — Correlate Haystack tags with BACnet points:** Mapping CSV/structs.
- **Day 54 — Haystack capstone:** `niagara-read` CLI with clap flags.

---

### Week 7 — RDF Bridge in Rust (Not rdflib)  
*Triples, IRIs, Turtle, adjacency graphs*

- **Day 55 — Why RDF after protocols:** Triples as Rust tuples/structs.
- **Day 56 — URIs & prefix maps:** `HashMap` QName expansion.
- **Day 57 — Triples & literals:** Enums for IRI vs typed literal.
- **Day 58 — Reading Turtle:** Syntax by hand; optional `oxrdf` stretch.
- **Day 59 — Adjacency-list graph:** Subject → edges in `HashMap`.
- **Day 60 — rdf:type & Brick taxonomy:** Class and subclass chains.
- **Day 61 — Haystack tags vs Brick graphs:** When tags vs mergeable RDF.

---

### Week 8 — Brick Models & Query Patterns in Rust  
*Hand-authored TTL, SPARQL mindset without SPARQL engine*

- **Day 62 — Hand-author Brick AHU model:** `ahu1.ttl` capstone piece.
- **Day 63 — Pattern matching queries:** Tiny `SELECT`-style loops over graph.
- **Day 64 — Multi-protocol PCAP challenge:** One file, three Wireshark filters.
- **Day 65 — open-fdd drivers & semantic layer:** Transport → driver → RDF.
- **Day 66 — Serialize graph to Turtle:** Round-trip from Rust structures.
- **Day 67 — ASHRAE 223P alignment (concept):** Brick, Haystack, 223P roles.

---

### Week 9 — Live Data → Graph & Agent-Ready Export  
*Integrate BACnet reads with RDF; JSON for tools*

- **Day 68 — BACnet read → RDF triples:** Live snapshot into graph.
- **Day 69 — FILTER & OPTIONAL patterns:** Numeric filter; missing edges.
- **Day 70 — UNION & ASK queries:** Existence checks for commissioning.
- **Day 71 — DISTINCT, ORDER BY, LIMIT:** Practical query hygiene.
- **Day 72 — Haystack → RDF export path:** Zinc rows to triples stub.
- **Day 73 — Agent-ready metadata:** `serde_json` point rows for MCP/agents.

---

### Week 10 — Course Synthesis & Final Capstone  
*Portfolio: Rust CLIs + TTL + pcaps + review*

- **Day 74 — Course review:** Python → Rust → Wireshark → graph doc.
- **Day 75 — Final capstone:** Multi-protocol semantic snapshot; Wireshark filters documented in `pcaps/README.md`.

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
