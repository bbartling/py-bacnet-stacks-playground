# Py BACnet Stacks Playground

<p align="center">
  <a href="https://discord.gg/Ta48yQF8fC"><img src="https://img.shields.io/badge/Discord-Join%20Server-5865F2.svg?logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python"></a>
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT">
  <a href="vibe_code_apps_23/"><img src="https://img.shields.io/badge/active-vibe__code__apps__23-2ea44f" alt="Residential DSM lab"></a>
  <a href="vibe_code_apps_13/"><img src="https://img.shields.io/badge/active-vibe__code__apps__13-009966" alt="DIY BACnet router"></a>
  <a href="vibe_code_apps_16/"><img src="https://img.shields.io/badge/active-vibe__code__apps__16-009966" alt="Rust BACnet lab"></a>
  <a href="https://overthewire.org/wargames/bandit/"><img src="https://img.shields.io/badge/Linux-OverTheWire%20Bandit-FCC624?logo=linux&logoColor=black" alt="Bandit Linux"></a>
</p>

<p align="center">
  <a href="https://discord.gg/Ta48yQF8fC">
    <img src="https://img.shields.io/badge/Discord-daily%20challenges-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord daily challenges">
  </a>
  <a href="lessons/INDEX.md">
    <img src="https://img.shields.io/badge/Lessons-Days%201–75%20Python%20%2B%20Rust-2563EB?style=for-the-badge" alt="Lessons Days 1–75">
  </a>
  <a href="https://overthewire.org/wargames/bandit/">
    <img src="https://img.shields.io/badge/Linux-Bandit%20wargame-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="OverTheWire Bandit">
  </a>
  <a href="vibe_code_apps_23/">
    <img src="https://img.shields.io/badge/Vibe%2023-Residential%20DSM-2ea44f?style=for-the-badge" alt="Vibe 23 Residential DSM">
  </a>
  <a href="https://github.com/bbartling/py-bacnet-stacks-playground/pkgs/container/vibe19">
    <img src="https://img.shields.io/badge/GHCR-vibe19-0B7285?style=for-the-badge&logo=docker&logoColor=white" alt="GHCR vibe19">
  </a>
  <a href="vibe_code_apps_12/pdf/vibe12-edge-fdd-guide.pdf">
    <img src="https://img.shields.io/badge/Docs-PDF%20manual-DC2626?style=for-the-badge" alt="Docs PDF">
  </a>
</p>

Hands-on playground for **HVAC controls technicians, IoT practitioners, and building-systems tinkerers**: dual-language **Python + Rust** daily lessons (BACnet → networking → Haystack → RDF), vibe-code labs from field scripting to residential DSM, and Linux shell practice via [OverTheWire Bandit](https://overthewire.org/wargames/bandit/) with daily challenges on Discord.

Days **1–27** lead with Python + BACnet (BAC0 / BACpypes3) and a Rust companion. From **Day 28** the main text flips to Rust (Cargo, sockets, tcpdump/Wireshark, [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet), [rusty-haystack](https://github.com/jscott3201/rusty-haystack)) with a matching Python companion each day. Semantic weeks use RDF dual-stack **`rdflib` / `oxrdf`**.

---

<details>
<summary>Who this is for</summary>

## Who this is for

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet from the field and wants to code it in **Python and Rust**, play with **Wireshark**, and learn graph modeling (`rdflib` / `oxrdf`) with AI-assisted workflows

</details>

<details>
<summary>Learning paths</summary>

## Learning paths

| Track | What you get | Start here |
| --- | --- | --- |
| **Python + Rust (BACnet / networking / RDF)** | Days **1–75 dual-language**: shared scaffold every day; **1–27** Python-main + Rust companion; **28–75** Rust-main + Python companion; RDF weeks **`rdflib` + `oxrdf`** | [`lessons/`](lessons/) · [`lessons/INDEX.md`](lessons/INDEX.md) · Day 1: [`lessons/day01.md`](lessons/day01.md) |
| **Linux (OverTheWire Bandit)** | Shell / Linux fundamentals via [Bandit](https://overthewire.org/wargames/bandit/); **daily challenges on Discord** (same cadence as Python & Rust) | [`lessons/bandit/`](lessons/bandit/) · [Discord](https://discord.gg/Ta48yQF8fC) |
| **Grid-search DSM tutorials** | Ten progressive EnergyPlus ExampleFiles lessons (thermostat → BESS) supporting Vibe 23 | [`lessons/grid_search/`](lessons/grid_search/) · [`INDEX.md`](lessons/grid_search/INDEX.md) |
| **DIY BACnet router (app 13)** | Pi/Linux **BACnet/IP ↔ MS/TP** router; three-phase Rust lab | [`vibe_code_apps_13/`](vibe_code_apps_13/) · [AGENTS.md](vibe_code_apps_13/AGENTS.md) |
| **Open FDD Vibe Coder (app 19)** | Streamlit + pandas 50-rule cookbook lab *(completed reference)* | [`vibe_code_apps_19/`](vibe_code_apps_19/) |
| **OpenFDD WattLab (app 20)** | EnergyPlus ECM screens *(completed reference)* | [`vibe_code_apps_20/`](vibe_code_apps_20/) |
| **Demand twin (app 21)** | Liberty cooling DR twin *(completed reference)* | [`vibe_code_apps_21/`](vibe_code_apps_21/) |
| **Lakeside ES (app 22)** | Lakeside heating DSM / grid-search stack *(completed reference)* | [`vibe_code_apps_22/`](vibe_code_apps_22/) |
| **Residential DSM lab (app 23)** | Heat-pump home DR + thermostat/battery grid search | [`vibe_code_apps_23/`](vibe_code_apps_23/) |

</details>

<details>
<summary>Vibe code checkpoints</summary>

## Vibe code checkpoints

Hands-on milestones from BACnet scripting to cloud FDD. Checkpoints **1–10** are historical demos; featured builds are linked below.

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
| **11** | **[Agentic BAS from spec](vibe_code_apps_11/)** | Spec-driven BAS via **SKILL.md**, workspace memory, and cron-driven **Codex CLI** agent. | Paused |
| **12** | **[AI-assisted edge-to-cloud HVAC FDD](vibe_code_apps_12/)** | End-to-end HVAC FDD pipeline: BACnet discovery, RPM polling, AWS IoT Core MQTT, DynamoDB, Lambda, FDD Rule Lab. | Done |
| **13** | **[DIY BACnet router](vibe_code_apps_13/)** | Pi/Linux **BACnet/IP ↔ MS/TP** router in Rust (`rusty-bacnet`): wire test → mini-device → router appliance. | **Active** |
| **14** | **[BACnet routing research lab](vibe_code_apps_14/)** | BACpypes3 timed labs toward Misty3 and router-mstp. | **Active** |
| **15** | **[Rust embedded BACnet device](vibe_code_apps_15/)** | Embedded **Rust** BACnet on **STM32 NUCLEO-F401RE**; RS-485 / MS/TP lab. | **Active** |
| **16** | **[Rust BACnet stack lab](vibe_code_apps_16/)** | [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) server + probe; Open-FDD mimic; Feather concept. | **Active** |
| **17** | **[Project Haystack playground](vibe_code_apps_17/)** | Niagara **nHaystack**, [`rusty-haystack`](https://github.com/jscott3201/rusty-haystack), [`pyhaystack`](https://github.com/ChristianTremblay/pyhaystack). | **Active** |
| **18** | **[DIY BAS / Haystack data lake (Rust)](vibe_code_apps_18/)** · [Discussion #5](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5) | Read-only **`bas-haystack-lake-rs`**: collector, Postgres lake, admin API, Docker/CI. | **Active** |
| **19** | **[Open FDD Vibe Coder (Streamlit)](vibe_code_apps_19/)** | Streamlit + pandas twin of the [Open-FDD Pandas Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html). Container: `ghcr.io/bbartling/vibe19`. | Done |
| **20** | **[OpenFDD WattLab](vibe_code_apps_20/)** | EnergyPlus companion to vibe19: MeasureBriefs → Docker EP 26.1 → IDF patches → QA. | Done |
| **21** | **[Demand-management twin](vibe_code_apps_21/)** | Liberty Building cooling DR: G14 Twin → hourly E+ farm → sklearn `facility_kw`. | Done |
| **22** | **[Lakeside ES (unified)](vibe_code_apps_22/)** | Lakeside Elementary heating DSM / grid-search stack. | Done |
| **23** | **[Residential heat-pump DSM](vibe_code_apps_23/)** | Hypothetical heat-pump home: DR demo, TOU thermostat grid, battery co-optimization. | **Active** |

</details>

<details>
<summary>Computer Science Theory 101 — weekly outline</summary>

## Computer Science Theory 101 — weekly outline

AI-generated mini lessons as daily challenges with a **shared scaffold** (`Goal` → `Key Takeaway`, then a language companion). **Every day is Python and Rust**—only which side is “main” flips:

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

### Week 2 — Control Structures & Data Collection
*Part II: Loops, conditionals, functions, files · + Rust companions*

- **Day 8 — For Loops & Range:** Iterate over lists/strings/ranges, `enumerate()`. **Rust:** `for`, `0..n`, `.enumerate()`.
- **Day 9 — Conditionals & While Loops:** `if`/`elif`/`else`, `while`, sentinel loops. **Rust:** `if` expressions, `while`.
- **Day 10 — String Methods: Split, Join & Case:** `split()`, `join()`, case conversion. **Rust:** `.split`, `.collect`, `.to_uppercase()`.
- **Day 11 — Introducing Dictionaries:** Keys, values, add, retrieve, membership. **Rust:** `HashMap`, `.get` → `Option`.
- **Day 12 — Looping over Dictionaries:** `items()`, `keys()`, `values()` (no comprehensions). **Rust:** `for (k, v) in &map`.
- **Day 13 — Tuples & Sets (Light):** Immutable tuples, sets for membership (optional). **Rust:** tuples, arrays.
- **Day 14 — Loops & Sentinels:** `break`, `continue`, common loop patterns. **Rust:** same keywords.

### Week 3 — Functions, Modules & Files
*Part II continued: Reusable code, modules, file I/O · + Rust companions*

- **Day 15 — Writing Functions:** Define functions, parameters, return, docstrings. **Rust:** `fn`, typed params/returns.
- **Day 16 — Modules & the Standard Library:** `math`, `random`, organising code. **Rust:** `use std::...`, crates.
- **Day 17 — Reading & Writing Files:** `open()`, `with`, read/write text and CSV. **Rust:** `std::fs`.
- **Day 18 — Handling Errors:** `try`/`except`, robust programs. **Rust:** `Result`, `Option` preview.
- **Day 19 — Week 3 Review:** CSV of sensor readings, statistics, error handling. **Rust:** small review project.
- **Day 20 — Built-in Functions:** `min()`, `max()`, `sorted()`, `sum()`, `zip()` (no comprehensions). **Rust:** iterators.
- **Day 21 — Slicing & String Formatting:** Advanced f-strings, slicing. **Rust:** `format!`, slices.

### Week 4 — Data Structures & Discovery
*Part III: Lists, dicts, file I/O · + Rust companions*

- **Day 22 — Working with Nested Data:** Lists of dicts, dicts of lists (loops only, no comprehensions). **Rust:** `Vec` of `struct`.
- **Day 23 — Random & Math:** `random`, `math` for simulations. **Rust:** `rand` crate.
- **Day 24 — any(), all() & Simple Patterns:** Boolean checks on collections. **Rust:** `.any` / `.all`.
- **Day 25 — Documentation & help():** Docstrings, comments, `help()`. **Rust:** `///`, `cargo doc`.
- **Day 26 — Week 4 Review:** Nested data, built-ins, loops. **Rust:** map + alarm review.

### Week 5 — Rust Fast Track (After Python Day 27)
*Rust-main + Python companion each day — ownership, types, control flow, collections*

- **Day 27 — What Is an Algorithm? (HVAC & data):** Finite steps, inputs/outputs; **Rust:** ownership teaser (move vs `&`).
- **Day 28 — Rust recap & ownership crash course:** Confirm Cargo; **ownership, borrowing, lifetimes** intuition. **Python:** GC vs ownership companion.
- **Day 29 — Types, Operators & Variables:** Scalars, `mut`, formatting BACnet-style readings. **Python:** same readings with types/`f`-strings.
- **Day 30 — Control Flow:** `if`, loops, `match` for alarm/priority-style logic. **Python:** `if` / `match`/`case`.
- **Day 31 — Functions, Option & Result:** Error handling before sockets. **Python:** functions + exceptions / `Optional`.
- **Day 32 — struct, enum & impl:** Model BACnet points and object kinds. **Python:** dataclasses / Enum.
- **Day 33 — Vec, HashMap & String:** Device caches and tag maps. **Python:** list / dict.
- **Day 34 — Ownership & Borrowing (practice):** References for network buffers and APIs. **Python:** aliases / mutability companion.

### Week 5b — Network Programming & Wireshark
*UDP/TCP, tcpdump pcaps, display filters — Rust-main; Python companion mirrors sockets / capture workflow*

- **Day 35 — Network map:** BACnet UDP `:47808`, Haystack TCP `:443`, Modbus TCP—bench topology.
- **Day 36 — UDP sockets in Rust:** Echo lab; BACnet datagram mindset. **Python:** `socket` UDP echo.
- **Day 36b — Modbus TCP (beginner OT):** Register read over TCP `:502`/`:1502`; Wireshark `modbus` filter. **Python:** pymodbus / raw TCP sketch.
- **Day 37 — TCP client/server:** Echo lab; HTTP/TLS foundation. **Python:** `socket` TCP.
- **Day 38 — tcpdump & PCAP workflow:** `capture_pcap.sh`, snaplen, offline analysis.
- **Day 39 — Wireshark: BACnet on UDP:** BVLC/NPDU/APDU; filter `udp.port == 47808`.
- **Day 40 — Wireshark: TCP, TLS & HTTP:** Haystack preview; filter `tcp.port == 443`.

### Week 6 — rusty-bacnet Specialty
*Discovery, ReadProperty, RPM, writes (lab-safe), capstone CLI — Rust-main; Python companion via BAC0 / bacpypes3*

- **Day 41 — Intro rusty-bacnet:** Clone, build, map Who-Is/ReadProperty APIs.
- **Day 42 — ReadProperty:** Device **5007** bench read in Rust.
- **Day 43 — ReadPropertyMultiple:** Poll loops and traffic math.
- **Day 44 — WriteProperty & priority:** Lab/sim only; read-back discipline.
- **Day 45 — Who-Is / I-Am scan:** Discovery table in `HashMap`.
- **Day 46 — BACnet capstone:** Mini commission CLI + CSV snapshot.
- **Day 47 — Async preview (tokio):** Why edge services use async I/O. **Python:** `asyncio` sketch.

### Week 6b — rusty-haystack & HTTP Haystack Ops
*Niagara nHaystack, Basic vs SCRAM, fixtures, tag↔BACnet mapping — Rust-main; Python companion via requests/httpx*

- **Day 48 — HTTP mental model:** `/about`, `/read`, `/ops`; status codes.
- **Day 49 — rusty-haystack setup:** Build client; Niagara URL and TLS lab notes.
- **Day 50 — /read & Zinc filters:** Point reads and grid parsing.
- **Day 51 — Auth: Basic vs SCRAM:** Niagara `HTTPBasicScheme` vs Project Haystack SCRAM.
- **Day 52 — Golden fixtures:** Offline dev with captured Zinc/HTTP fixtures.
- **Day 53 — Correlate Haystack tags with BACnet points:** Mapping CSV/structs.
- **Day 54 — Haystack capstone:** `niagara-read` CLI with clap flags.

### Week 7 — RDF Bridge (rdflib + oxrdf)
*Triples, IRIs, Turtle, graphs — dual-stack*

- **Day 55 — Why RDF after protocols:** Triples; same sample on both stacks.
- **Day 56 — URIs & prefix maps:** QName expansion; shared prefixes.
- **Day 57 — Triples & literals:** IRI vs typed literal.
- **Day 58 — Reading Turtle:** Hand syntax; `oxrdf` / `rdflib` load.
- **Day 59 — Adjacency-list graph:** Subject → edges; parallel `rdflib` Graph.
- **Day 60 — rdf:type & Brick taxonomy:** Class and subclass chains.
- **Day 61 — Haystack tags vs Brick graphs:** When tags vs mergeable RDF.

### Week 8 — Brick Models & Query Patterns (rdflib + oxrdf)
*Hand-authored TTL; SPARQL intent on both stacks*

- **Day 62 — Hand-author Brick AHU model:** `ahu1.ttl` capstone piece.
- **Day 63 — Pattern matching queries:** Tiny `SELECT`-style patterns.
- **Day 64 — Multi-protocol PCAP challenge:** One file, three Wireshark filters.
- **Day 65 — open-fdd drivers & semantic layer:** Transport → driver → RDF.
- **Day 66 — Serialize graph to Turtle:** Round-trip with `oxrdf` / `rdflib`.
- **Day 67 — ASHRAE 223P alignment (concept):** Brick, Haystack, 223P roles.

### Week 9 — Live Data → Graph & Agent-Ready Export
*BACnet → RDF; SPARQL FILTER/ASK; JSON for tools*

- **Day 68 — BACnet read → RDF triples:** Live snapshot into graph.
- **Day 69 — FILTER & OPTIONAL patterns:** Same SPARQL on both stacks.
- **Day 70 — UNION & ASK queries:** Existence checks for commissioning.
- **Day 71 — DISTINCT, ORDER BY, LIMIT:** Practical query hygiene.
- **Day 72 — Haystack → RDF export path:** Zinc rows to triples stub.
- **Day 73 — Agent-ready metadata:** JSON/NDJSON point rows for MCP/agents.

### Week 10 — Course Synthesis & Final Capstone
*Portfolio: dual-language CLIs + TTL + pcaps + `rdflib` SPARQL / `oxrdf` graph-export*

- **Day 74 — Course review:** Python → Rust → Wireshark → dual-stack graph doc.
- **Day 75 — Final capstone:** Multi-protocol semantic snapshot; `oxrdf` in `graph-export`; `rdflib` SPARQL on `ahu1.ttl`; Wireshark filters in `pcaps/README.md`.

</details>

<details>
<summary>Linux training — OverTheWire Bandit</summary>

## Linux training — OverTheWire Bandit

Linux / shell fundamentals use **[OverTheWire Bandit](https://overthewire.org/wargames/bandit/)** — not a local LFCS day pack.

| Item | Link |
| --- | --- |
| **Play Bandit** | [overthewire.org/wargames/bandit](https://overthewire.org/wargames/bandit/) · start at [Level 0](https://overthewire.org/wargames/bandit/bandit0.html) |
| **Repo pointer** | [`lessons/bandit/README.md`](lessons/bandit/README.md) |
| **Daily challenges** | Posted on **[Discord](https://discord.gg/Ta48yQF8fC)** — same pattern as the Python and Rust lesson posts |

Bandit teaches the command-line basics (SSH, files, permissions, pipes, processes) that everything else in this repo assumes. When stuck: `man <command>`, `help <builtin>`, then ask on Discord.

**Related EnergyPlus tutorials:** bounded DSM grid-search labs live at [`lessons/grid_search/`](lessons/grid_search/) and support the active [Vibe 23 residential DSM studio](vibe_code_apps_23/).

</details>

<details>
<summary>💛 Support This Work</summary>

If this playground saves you time or budget, or helps with BAS / BACnet / DSM learning, you can support continued open-source development through PayPal. Your contribution directly helps fund the monthly time and labor required to keep the project moving forward. Your support is greatly appreciated.

<p align="center">
  <a href="https://paypal.me/benbartling20/25"><img src="https://img.shields.io/badge/Donate-$25-0070BA?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate $25 via PayPal"></a>
  <a href="https://paypal.me/benbartling20/50"><img src="https://img.shields.io/badge/Donate-$50-0070BA?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate $50 via PayPal"></a>
  <a href="https://paypal.me/benbartling20/250"><img src="https://img.shields.io/badge/Donate-$250-0070BA?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate $250 via PayPal"></a>
  <a href="https://paypal.me/benbartling20"><img src="https://img.shields.io/badge/Donate-Custom%20Amount-0070BA?style=for-the-badge&logo=paypal&logoColor=white" alt="Choose a custom PayPal donation amount"></a>
</p>

</details>

## License

MIT — see [LICENSE](LICENSE).
