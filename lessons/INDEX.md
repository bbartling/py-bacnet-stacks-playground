# Lessons index (Days 1–71)

Daily mini-lessons live in this folder as `dayNN.md`. The **Weekly Outline** in the repo [README.md](../README.md#weekly-outline) is the canonical syllabus text; this page is a **compact link hub**.

**Conventions:** Early days avoid list/dict comprehensions. **Days 41–43** (optional) are **hobby** grid/stack/maze lessons tied to **maze-algorithm-sandbox**. **Days 44–71** introduce tuples, sets, nested dicts, RDF/Turtle/`rdflib`, Brick, and SPARQL as needed for smart-building **data modeling** (not a full graph-algorithms course).

---

## Using this track as **coding challenges** (students implement themselves)

**Yes — if you treat the written lesson as the spec, not the solution.** Almost every `dayNN.md` already includes **Micro exercises** (and often **Mini examples** / **How to use it** steps) that expect students to **open an editor and write Python** (or Turtle / SPARQL in the RDF weeks), not only read prose.

| What is already there | How to turn it into a “challenge” |
| --- | --- |
| **Micro exercises** (numbered lists) | Require a **single `.py` per day** (or per week bundle) that implements those functions; add **one hidden test CSV** or **assert** cases you keep private for grading. |
| **“How to use it”** scripted steps (e.g. Day 19) | Treat as a **mini-spec**: students submit `main`, functions, and sample `data.csv`; deduct points if error handling is missing. |
| **Algorithms days (27–40)** | Strong for **from-scratch** work: re-implement `linear_search`, `running_mean`, Boolean rules, Euler step — forbid importing `pandas`/`numpy` where the lesson says plain Python. |
| **Optional maze days (41–43)** | Treat as **extra credit**: grid neighbors, DFS/stack walk, iterative maze generator; no BACnet dependency. |
| **Capstone-style days** | **Day 19** (CSV + functions), **Day 40** (parallel lists + fault timeline), **Day 71** (`capstone.ttl` + SPARQL files) are natural **graded milestones**. |
| **Concept-only days** (e.g. 27, 44, 51) | Assign **short deliverables**: pseudocode, 5-sentence reading notes, *or* one tiny function that encodes the idea (e.g. `expand(prefix_map, qname)` on Day 46). |

**Difficulty knobs (optional):** (1) Ban a built-in the lesson allows (`sum`, `sorted`) for one week to force loop practice. (2) Add **type hints** or **docstrings** as part of the rubric. (3) Require **small unit tests** written by the student from Week 3 onward.

**Realism:** Days **55–71** assume **`pip install rdflib`**; SPARQL quirks vary by `rdflib` version — allow “post-process in Python” fallbacks where the lesson already says so. That keeps challenges **fair** without becoming a SPARQL engine course.

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

## Week 5 — Algorithms & HVAC data (Part A)

| Day | Link |
| --- | --- |
| 27 | [day27.md](./day27.md) |
| 28 | [day28.md](./day28.md) |
| 29 | [day29.md](./day29.md) |
| 30 | [day30.md](./day30.md) |
| 31 | [day31.md](./day31.md) |
| 32 | [day32.md](./day32.md) |
| 33 | [day33.md](./day33.md) |

## Week 6 — Algorithms, FDD logic, thermal lite, capstone

| Day | Link |
| --- | --- |
| 34 | [day34.md](./day34.md) |
| 35 | [day35.md](./day35.md) |
| 36 | [day36.md](./day36.md) |
| 37 | [day37.md](./day37.md) |
| 38 | [day38.md](./day38.md) |
| 39 | [day39.md](./day39.md) |
| 40 | [day40.md](./day40.md) |

## Optional — Grid & maze hobby (after Day 40, before RDF)

| Day | Link |
| --- | --- |
| 41 | [day41.md](./day41.md) |
| 42 | [day42.md](./day42.md) |
| 43 | [day43.md](./day43.md) |

## Week 7 — Python bridge for RDF (smart buildings)

| Day | Link |
| --- | --- |
| 44 | [day44.md](./day44.md) |
| 45 | [day45.md](./day45.md) |
| 46 | [day46.md](./day46.md) |
| 47 | [day47.md](./day47.md) |
| 48 | [day48.md](./day48.md) |
| 49 | [day49.md](./day49.md) |
| 50 | [day50.md](./day50.md) |

## Week 8 — RDF & Turtle (`rdflib`)

| Day | Link |
| --- | --- |
| 51 | [day51.md](./day51.md) |
| 52 | [day52.md](./day52.md) |
| 53 | [day53.md](./day53.md) |
| 54 | [day54.md](./day54.md) |
| 55 | [day55.md](./day55.md) |
| 56 | [day56.md](./day56.md) |
| 57 | [day57.md](./day57.md) |

## Week 9 — Brick on RDF

| Day | Link |
| --- | --- |
| 58 | [day58.md](./day58.md) |
| 59 | [day59.md](./day59.md) |
| 60 | [day60.md](./day60.md) |
| 61 | [day61.md](./day61.md) |
| 62 | [day62.md](./day62.md) |
| 63 | [day63.md](./day63.md) |

## Week 10 — SPARQL for Brick graphs

| Day | Link |
| --- | --- |
| 64 | [day64.md](./day64.md) |
| 65 | [day65.md](./day65.md) |
| 66 | [day66.md](./day66.md) |
| 67 | [day67.md](./day67.md) |
| 68 | [day68.md](./day68.md) |
| 69 | [day69.md](./day69.md) |
| 70 | [day70.md](./day70.md) |
| 71 | [day71.md](./day71.md) |

---

## Optional dependencies

- **`rdflib`** (from about Day 55): `pip install rdflib`

## Related repos (external)

- **open-fdd** — expression rules, Pandas engine: see your clone’s `docs/expression_rule_cookbook.md` when lessons reference FDD patterns.
