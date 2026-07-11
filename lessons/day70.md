# Day 70 – UNION & ASK Queries

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Same commissioning checks on both stacks: **`ASK`** (exists?) and **`UNION`** (merge two patterns).

## Concept

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex:    <http://example.org/>
ASK {
  ex:AHU1 brick:hasPoint ?p .
  ?p a brick:Supply_Air_Temperature_Sensor .
}
```

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex:    <http://example.org/>
SELECT ?p WHERE {
  { ex:AHU1 brick:hasPoint ?p . ?p a brick:Supply_Air_Temperature_Sensor }
  UNION
  { ex:AHU1 brick:hasPoint ?p . ?p a brick:Outside_Air_Temperature_Sensor }
}
```

## Why This Matters

Commissioning scripts ask yes/no before trends—**ASK** is first-class, not only SELECT tables.

## Mini Examples

- ASK: does AHU1 have a SAT-typed point?
- UNION: one list from two sensor-class patterns.

## Micro Exercises

1. Three ASK rules on `ahu1.ttl` (both stacks).
2. UNION for two sensor classes; print PASS/FAIL markdown.
3. Compare bool results Rust vs Python.

## Key Takeaway

**Existence checks are first-class**—not everything is a result table.

---

## Python companion — same ASK / UNION

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from rdflib import Graph

g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
ask = g.query("""
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex: <http://example.org/>
ASK { ex:AHU1 brick:hasPoint ?p . ?p a brick:Supply_Air_Temperature_Sensor }
""")
print("ASK", bool(ask))
```

| Rust (`oxrdf`) | Python (`rdflib`) |
|--------|--------|
| Same ASK / UNION intent | `g.query` ASK → `bool(...)` |
| PASS/FAIL report | Same checks |

**Takeaway:** ASK is yes/no; UNION merges patterns—same queries on both sides.
