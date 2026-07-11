# Day 62 – Hand-Author Brick Model for One AHU

## Goal

Write **`ahu1.ttl`** by hand for one AHU, SAT, OAT, and **`brick:hasPoint` / `brick:feeds`** (if applicable).

## Concept

Minimum entities:

- `ex:AHU1` a `brick:AHU`
- Points: SAT, OAT as appropriate sensor classes
- Optional: `ex:VAV1 brick:isFedBy ex:AHU1` if in scope

Load into Day 59 graph; verify counts.

**Starter file:** extend [`capstone/model/ahu1.ttl`](./capstone/model/ahu1.ttl) (N4 `v4Fifteen` bench naming).

## Why This Matters

Commissioning deliverables increasingly include **semantic models** alongside BACnet point lists.

## Mini Examples

- Validate Turtle with online parser or `oxrdf` load.
- Pretty-print via your Display impl.

## Micro Exercises

1. At least 8 triples in TTL file.
2. Query all points of AHU1 from Rust graph code.
3. Screenshot Turtle + Rust query output for portfolio.

## Key Takeaway

**Small accurate models beat huge auto-generated junk**—hand authoring builds intuition.

---

## Python companion — Tiny TTL sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from pathlib import Path

ttl = """@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ex: <http://example.org/> .
ex:AHU1 a brick:AHU .
ex:AHU1 brick:hasPoint ex:AHU1-SAT .
"""
Path("~/py-lab/ahu1_sketch.ttl").expanduser().write_text(ttl)
# Load/query that file in Rust (Day 59+ graph)—not rdflib.
```

| Rust (main lesson) | Python |
|--------|--------|
| Hand-author + load `ahu1.ttl` into graph | `pathlib` write a few Turtle lines |
| Query points in Rust | parallel file sketch only |

**Takeaway:** Authoring Turtle is text—Python can draft it; the course track loads and queries in Rust.
