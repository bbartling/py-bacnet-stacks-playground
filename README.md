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
    <img src="https://img.shields.io/badge/Lessons-Days%201–112%20Rust%20Networking-2563EB?style=for-the-badge" alt="Rust networking lessons Days 1–112">
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

Hands-on playground for **HVAC controls technicians, IoT practitioners, and building-systems tinkerers**: a **112-day Rust-first network programming course**, building-automation experiments, and Linux shell practice.

The [networking course](lessons/INDEX.md) goes from Rust fundamentals through IPv4/IPv6, packet parsing, UDP/TCP, async services, Modbus, BACnet routing, and Raspberry Pi labs. Build a TCP proxy, a pocket router/WAP, and finish with a contribution to **DIY BACnet Router**. Python companions are optional test peers and comparisons. Weekly review projects leave the implementation to you; RDF/Brick/Haystack are separate electives.

**Already at the old Day 19?** Keep your completed work and continue with [Day 20](lessons/day20.md), porting your own project to Rust. All 112 lesson plans are written; [validation notes](lessons/VALIDATION.md) distinguish checked examples from learner-run hardware labs.

---

<details>
<summary>Who this is for</summary>

## Who this is for

- **HVAC controls technicians** who want to automate scans, collect data, and build simple tools
- **IoT practitioners** working with building automation
- **Anyone** who knows BACnet/Modbus from the field and wants to learn **Rust**, understand packets in **Wireshark**, and build network tools and router labs

</details>

<details>
<summary>Learning paths</summary>

## Learning paths

| Track | What you get | Start here |
| --- | --- | --- |
| **Rust network programming** | **112 days**, 16 review projects: Rust, IPv4/IPv6, packets, UDP/TCP, async proxy, Modbus, BACnet, Pi router/WAP and MS/TP; Python optional | [Course index](lessons/INDEX.md) · [Lab guide](lessons/LAB_GUIDE.md) · [Day 1](lessons/day01.md) |
| **Linux (OverTheWire Bandit)** | Shell / Linux fundamentals via [Bandit](https://overthewire.org/wargames/bandit/); **daily challenges on Discord** (same cadence as Python & Rust) | [`lessons/bandit/`](lessons/bandit/) · [Discord](https://discord.gg/Ta48yQF8fC) |
| **Grid-search DSM tutorials** | Ten progressive EnergyPlus ExampleFiles lessons (thermostat → BESS) supporting Vibe 23 | [`lessons/grid_search/`](lessons/grid_search/) · [`INDEX.md`](lessons/grid_search/INDEX.md) |
| **DIY BACnet router (app 13)** | Pi/Linux **BACnet/IP ↔ MS/TP** router; three-phase Rust lab | [`vibe_code_apps_13/`](vibe_code_apps_13/) · [AGENTS.md](vibe_code_apps_13/AGENTS.md) |
| **Open FDD Vibe Coder (app 19)** | Streamlit + pandas 50-rule cookbook lab *(completed reference)* | [`vibe_code_apps_19/`](vibe_code_apps_19/) |
| **OpenFDD WattLab (app 20)** | EnergyPlus ECM screens *(completed reference)* | [`vibe_code_apps_20/`](vibe_code_apps_20/) |
| **Demand twin (app 21)** | Liberty cooling DR twin *(completed reference)* | [`vibe_code_apps_21/`](vibe_code_apps_21/) |
| **Lakeside ES (app 22)** | Lakeside heating DSM / grid-search stack *(completed reference)* | [`vibe_code_apps_22/`](vibe_code_apps_22/) |
| **Residential DSM lab (app 23)** | Heat-pump home DR + thermostat/battery grid search | [`vibe_code_apps_23/`](vibe_code_apps_23/) |
| **Live BACnet twin (app 24)** | Priority-array RTU twin + BAS mimic (`SURROGATE_PLANT_V1`) | [`vibe_code_apps_24/`](vibe_code_apps_24/) |
| **PID hunting tutorial (app 25)** | Open-FDD PID-HUNT-1 notebook + synthetic AO math | [`vibe_code_apps_25/`](vibe_code_apps_25/) |

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
| **24** | **[Live BACnet + physics twin](vibe_code_apps_24/)** | FastAPI BAS mimic + optional BACnet; priority-8 UI writes; `SURROGATE_PLANT_V1`. | **Active** |
| **25** | **[Open-FDD PID hunting tutorial](vibe_code_apps_25/)** | Jupyter + PyPI `open-fdd`: synthetic AO hunting, PID-HUNT-1 math, AND-gate viz. | **Active** |

</details>

<details>
<summary>Rust network programming — weekly outline</summary>

<a id="computer-science-theory-101-weekly-outline"></a>

## Rust network programming — weekly outline

The [course index](lessons/INDEX.md) is the canonical syllabus. Rust is required; Python companions are optional. A study day is a session, not a calendar deadline. Reviews can span a weekend. There are no full review solutions in the lesson pages.

| Week | Days | Focus |
| --- | --- | --- |
| 1 | [1–7](lessons/day01.md) | Rust setup, values, strings and collections |
| 2 | [8–14](lessons/day08.md) | Control flow, text records and identity |
| 3 | [15–21](lessons/day15.md) | Functions, files, Day 19 review and Rust bridge |
| 4 | [22–28](lessons/day22.md) | Ownership, types, CLI design and tests |
| 5 | [29–35](lessons/day29.md) | IPv4/IPv6, routes, neighbors and DNS |
| 6 | [36–42](lessons/day36.md) | Binary codecs, packet inspection and Wireshark |
| 7 | [43–49](lessons/day43.md) | UDP discovery, correlation and fault injection |
| 8 | [50–56](lessons/day50.md) | TCP streams, framing, half-close and bounded service |
| 9 | [57–63](lessons/day57.md) | Async Rust, cancellation and TCP traffic switch |
| 10 | [64–70](lessons/day64.md) | Modbus TCP/RTU framing and read-only toolkit |
| 11 | [71–77](lessons/day71.md) | BACnet BVLC/NPDU/APDU and rusty-bacnet |
| 12 | [78–84](lessons/day78.md) | Transactions, segmentation, COV and failure handling |
| 13 | [85–91](lessons/day85.md) | BACnet routing, BBMD and isolated network labs |
| 14 | [92–98](lessons/day92.md) | Pi pocket router/WAP, DHCP, DNS and forwarding |
| 15 | [99–105](lessons/day99.md) | Serial, RS-485, MS/TP and measured evidence |
| 16 | [106–112](lessons/day106.md) | DIY BACnet Router study and contribution |

Supporting material: [lab guide](lessons/LAB_GUIDE.md), [wire contracts](lessons/WIRE_FORMATS.md), [offline fixtures](lessons/fixtures/README.md), [topologies](lessons/TOPOLOGIES.md), [capture filters](lessons/lab-scripts/wireshark_filters.md), and [project briefs](lessons/capstone/README.md).

The old 75-day lesson files were replaced directly; no archive is kept. Existing unrelated semantic-modeling and application projects remain available as electives. Live hardware and image gates require their own evidence.

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
