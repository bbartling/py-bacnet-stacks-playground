# Lessons index (Days 1–75)

Daily mini-lessons live in this folder as `dayNN.md`. The **Weekly Outline** in the repo [README.md](../README.md#computer-science-theory-101-weekly-outline) is the canonical syllabus text; this page is a **compact link hub**.

**Conventions:** Same section scaffold throughout (`# Day NN`, then `## Goal` / `## Concept` / `## Why This Matters` / `## Mini Examples` / `## Micro Exercises` / `## Key Takeaway`, optional `## Wireshark Lab`, then companion). Days **1–27** are **Python + BACnet** (early days avoid list/dict comprehensions), each with a **Rust companion** at the bottom (install Rust on **Day 1**). Days **28–75** are **Rust-main** (Day 28 ownership/borrowing/lifetimes; then network programming UDP/TCP, **tcpdump/Wireshark labs**, **rusty-bacnet**, **rusty-haystack**, and **RDF dual-stack: `rdflib` (Python) + `oxrdf` (Rust)**—same Turtle samples and SPARQL/`SELECT`/`ASK`/`CONSTRUCT` intent on both where queries appear), each with a **Python companion** at the bottom for parallel learning. Lab scripts: [`lab-scripts/`](./lab-scripts/). **Capstone starters:** [`capstone/`](./capstone/).

---

## Using this track as **coding challenges** (students implement themselves)

**Yes — if you treat the written lesson as the spec, not the solution.** Almost every `dayNN.md` includes **Micro exercises** that expect students to **open an editor and write code**, not only read prose.

| What is already there | How to turn it into a “challenge” |
| --- | --- |
| **Micro exercises** | Require a **single Rust binary or module per day** (Days 28+) or **`.py` per day** (Days 1–27); add private test cases for grading. |
| **Wireshark Lab** (Days 35–40, 36b, 41–46, 48–54, 64, 75) | Require **`pcaps/` artifact** + screenshot with the lesson’s **display filter** pasted into Wireshark. |
| **Network labs** | Run [`capture_pcap.sh`](./lab-scripts/capture_pcap.sh) during the exercise; filter cheat sheet: [`wireshark_filters.md`](./lab-scripts/wireshark_filters.md). |
| **Capstone days** | **Day 46** (BACnet CLI), **Day 54** (Haystack CLI), **Day 75** (multi-protocol semantic snapshot) are graded milestones. |
| **RDF weeks (55–75)** | Hand-authored **`ahu1.ttl`**; dual-stack **`rdflib` (Python) + `oxrdf` (Rust)**; SPARQL shown on both where applicable; optional `serde_json`. |

**Difficulty knobs (optional):** (1) Ban `unwrap()` on network paths for one week. (2) Require **`cargo test`** from Week 6 onward. (3) Require **`clap --help`** UX on capstone CLIs.

---

## Week 1 — Fundamentals & first BACnet touch

| Day | Link |
| --- | --- |
| 1 | [day01.md](./day01.md) |
| 2 | [day02.md](./day02.md) |
| 3 | [day03.md](./day03.md) |
| 4 | [day04.md](./day04.md) |
| 5 | [day05.md](./day05.md) |
| 6 | [day06.md](./day06.md) |
| 7 | [day07.md](./day07.md) |

## Week 2 — Control structures & data collection

| Day | Link |
| --- | --- |
| 8 | [day08.md](./day08.md) |
| 9 | [day09.md](./day09.md) |
| 10 | [day10.md](./day10.md) |
| 11 | [day11.md](./day11.md) |
| 12 | [day12.md](./day12.md) |
| 13 | [day13.md](./day13.md) |
| 14 | [day14.md](./day14.md) |

## Week 3 — Functions, modules & files

| Day | Link |
| --- | --- |
| 15 | [day15.md](./day15.md) |
| 16 | [day16.md](./day16.md) |
| 17 | [day17.md](./day17.md) |
| 18 | [day18.md](./day18.md) |
| 19 | [day19.md](./day19.md) |
| 20 | [day20.md](./day20.md) |
| 21 | [day21.md](./day21.md) |

## Week 4 — Data structures & discovery

| Day | Link |
| --- | --- |
| 22 | [day22.md](./day22.md) |
| 23 | [day23.md](./day23.md) |
| 24 | [day24.md](./day24.md) |
| 25 | [day25.md](./day25.md) |
| 26 | [day26.md](./day26.md) |

## Week 5 — Algorithms pivot + Rust fast track

| Day | Link |
| --- | --- |
| 27 | [day27.md](./day27.md) — What is an algorithm? (Python); **pivot to Rust** |
| 28 | [day28.md](./day28.md) — Install Rust & Cargo |
| 29 | [day29.md](./day29.md) — Types, operators & variables |
| 30 | [day30.md](./day30.md) — Control flow: if, loop, match |
| 31 | [day31.md](./day31.md) — Functions, Option & Result |
| 32 | [day32.md](./day32.md) — struct, enum & impl |
| 33 | [day33.md](./day33.md) — Vec, HashMap & String |
| 34 | [day34.md](./day34.md) — Ownership & borrowing (fast track) |

## Week 5b — Network programming & Wireshark

| Day | Link |
| --- | --- |
| 35 | [day35.md](./day35.md) — Network map (UDP/TCP/ports) |
| 36 | [day36.md](./day36.md) — UDP sockets echo lab |
| 36b | [day36b_modbus_tcp.md](./day36b_modbus_tcp.md) — **Modbus TCP** register read (beginner OT) |
| 37 | [day37.md](./day37.md) — TCP client/server echo |
| 38 | [day38.md](./day38.md) — tcpdump & PCAP workflow |
| 39 | [day39.md](./day39.md) — Wireshark: BACnet on UDP |
| 40 | [day40.md](./day40.md) — Wireshark: TCP, TLS & HTTP |

## Week 6 — rusty-bacnet specialty

| Day | Link |
| --- | --- |
| 41 | [day41.md](./day41.md) — Intro rusty-bacnet |
| 42 | [day42.md](./day42.md) — ReadProperty (device 5007) |
| 43 | [day43.md](./day43.md) — ReadPropertyMultiple & polling |
| 44 | [day44.md](./day44.md) — WriteProperty & priority (lab-safe) |
| 45 | [day45.md](./day45.md) — Who-Is / I-Am discovery |
| 46 | [day46.md](./day46.md) — BACnet capstone CLI |
| 47 | [day47.md](./day47.md) — Async preview (tokio) |

## Week 6b — rusty-haystack & HTTP Haystack ops

| Day | Link |
| --- | --- |
| 48 | [day48.md](./day48.md) — HTTP mental model |
| 49 | [day49.md](./day49.md) — rusty-haystack client setup |
| 50 | [day50.md](./day50.md) — /read & Zinc filters |
| 51 | [day51.md](./day51.md) — Auth: Basic vs SCRAM |
| 52 | [day52.md](./day52.md) — Golden fixtures |
| 53 | [day53.md](./day53.md) — Haystack ↔ BACnet mapping |
| 54 | [day54.md](./day54.md) — Haystack capstone CLI |

## Week 7 — RDF bridge (rdflib + oxrdf)

| Day | Link |
| --- | --- |
| 55 | [day55.md](./day55.md) — Why RDF after protocols |
| 56 | [day56.md](./day56.md) — URIs & prefix maps |
| 57 | [day57.md](./day57.md) — Triples & literals |
| 58 | [day58.md](./day58.md) — Reading Turtle |
| 59 | [day59.md](./day59.md) — Adjacency-list graph |
| 60 | [day60.md](./day60.md) — rdf:type & Brick taxonomy |
| 61 | [day61.md](./day61.md) — Haystack tags vs Brick graphs |

## Week 8 — Brick models & query patterns (rdflib + oxrdf)

| Day | Link |
| --- | --- |
| 62 | [day62.md](./day62.md) — Hand-author Brick AHU model |
| 63 | [day63.md](./day63.md) — Pattern matching queries |
| 64 | [day64.md](./day64.md) — Multi-protocol PCAP challenge |
| 65 | [day65.md](./day65.md) — open-fdd drivers & semantic layer |
| 66 | [day66.md](./day66.md) — Serialize graph to Turtle |
| 67 | [day67.md](./day67.md) — ASHRAE 223P alignment (concept) |

## Week 9 — Live data → graph & agent export (rdflib + oxrdf)

| Day | Link |
| --- | --- |
| 68 | [day68.md](./day68.md) — BACnet read → RDF triples |
| 69 | [day69.md](./day69.md) — FILTER & OPTIONAL patterns |
| 70 | [day70.md](./day70.md) — UNION & ASK queries |
| 71 | [day71.md](./day71.md) — DISTINCT, ORDER BY, LIMIT |
| 72 | [day72.md](./day72.md) — Haystack → RDF export path |
| 73 | [day73.md](./day73.md) — Agent-ready JSON metadata |

## Week 10 — Course synthesis & final capstone

| Day | Link |
| --- | --- |
| 74 | [day74.md](./day74.md) — Course review |
| 75 | [day75.md](./day75.md) — Final capstone: semantic snapshot |

---

## Optional dependencies

- **Rust** (from Day 28): [rustup.rs](https://rustup.rs/)
- **tcpdump**, **Wireshark** (from Day 38): system packages
- **Optional crates** (stretch): `oxrdf`, `serde`, `serde_json`, `tokio`, `clap`
- **Python** (Days 1–27): `BAC0`, `bacpypes3` as in Day 1
- **Python RDF** (Days 55–75 companion): `rdflib` (`pip install rdflib`)

## Related repos (external)

- **[rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)** — Rust BACnet stack (Days 41–47)
- **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)** — Rust Haystack client/server (Days 48–54)
- **[nhaystack-niagara-pi-tutorial](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/)** — Niagara lab + golden fixtures
- **open-fdd** — edge drivers, FDD rules, agent workflows (Days 65, 73)

## Lab scripts

| Script | Purpose |
| --- | --- |
| [capture_pcap.sh](./lab-scripts/capture_pcap.sh) | Timed tcpdump capture to `lessons/pcaps/` |
| [wireshark_filters.md](./lab-scripts/wireshark_filters.md) | Per-day display filter cheat sheet |

## Capstone portfolio ([capstone/](./capstone/))

| Artifact | Days | Link |
| --- | --- | --- |
| Modbus read CLI starter | 36b | [modbus-read/](./capstone/modbus-read/) |
| BACnet CLI skeleton | 46 | [discover-and-poll/](./capstone/discover-and-poll/) |
| Haystack CLI tutorial | 54 | [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) |
| Brick TTL starter | 62 | [model/ahu1.ttl](./capstone/model/ahu1.ttl) |
| Graph export | 66, 68, 75 | [graph-export/](./capstone/graph-export/) |
| PCAP + review templates | 64, 74, 75 | [pcaps/README.md](./capstone/pcaps/README.md) · [COURSE_REVIEW.md](./capstone/COURSE_REVIEW.md) |
