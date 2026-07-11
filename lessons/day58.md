# Day 58 – Reading Turtle (By Hand, Then Parse Lite)

## Goal

Read **Turtle** syntax and optionally parse a tiny file with a minimal line-based approach or **`rio_turtle`** / **`oxrdf`** crate (pick one for stretch).

## Concept

```turtle
@prefix ex: <http://example.com/bldg#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .

ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:SAT .

ex:SAT a brick:Supply_Air_Temperature_Sensor .
```

Punctuation: `.` terminates; `;` continues same subject; `,` object list.

## Why This Matters

Brick models ship as **`.ttl` files**—you must read them even if Rust code builds graphs programmatically.

## Mini Examples

- Rewrite one block using full IRIs only (no prefixes).
- Count triples in a 10-line file by hand.

## Micro Exercises

1. Write `mini.ttl` for one equip + one point.
2. Optional: `cargo add oxrdf` and parse `mini.ttl` in 20 lines.
3. Compare to Haystack Zinc—what's easier for humans?

## Key Takeaway

**Turtle is the human-friendly RDF syntax**—Rust stores the parsed graph in memory structures from Days 57–59.

---

## Python companion — Write mini.ttl

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from pathlib import Path

ttl = """@prefix ex: <http://example.com/bldg#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .
ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:SAT .
ex:SAT a brick:Supply_Air_Temperature_Sensor .
"""
Path("~/py-lab/mini.ttl").expanduser().write_text(ttl)
# Load/query in Rust (oxrdf / adjacency graph)—not rdflib for the course track.
```

| Rust (main lesson) | Python |
|--------|--------|
| hand-read / `oxrdf` parse | `pathlib` write Turtle text |
| graph in memory structs | file draft only |
| course prefers Rust RDF | rdflib only as contrast |

**Takeaway:** Authoring Turtle is text—Python can draft `mini.ttl`; parse and store it in Rust.
