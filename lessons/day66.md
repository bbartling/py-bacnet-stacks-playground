## Day 66 — Haystack tags vs Brick RDF graphs

### Goal

Contrast **Haystack** (tagged dicts / Zinc /Refs—**semi-structured**) with **Brick** (**RDF graph**, mergeable across sites). Neither replaces the other in the field; **bridges** exist (project Haystack *relationships* and Brick alignment efforts—mention at high level only).

### Concept

- **Tags** answer: “What is this point?” quickly in a **single** document.
- **Brick** answers: “How does this point relate to **equipment**, **spaces**, and **other points** across **datasets**?”

### Why this matters

Your **Python** course avoided Pandas; in operations you still see **CSV + tags**. RDF is the **interchange** shape when semantic interoperability matters (utilities, campus digital twins, FDD graph workshops).

### Mini exercises

1. Model the same SAT as (a) a Haystack-style `dict` with `dis`, `point`, `equipRef` keys vs (b) two Brick triples—side by side in notes.
2. Which representation is easier to **`git diff`** when a VAV is moved from one AHU to another?
3. One sentence: why **SPARQL** is unnecessary for a single tagged JSON file but useful for a **merged** campus graph.

### Key takeaway

**Tags = local convenience; RDF = global composition.** You will use both in real stacks.
