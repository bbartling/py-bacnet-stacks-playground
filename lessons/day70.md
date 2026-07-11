# Day 70 – UNION & ASK Queries

## Goal

Implement **`UNION`** (two patterns, merge results) and **`ASK`** (exists?) for commissioning checks.

## Concept

ASK example: "Does AHU1 have any Supply Air Temperature sensor?"

```rust
fn ask_has_sat(g: &AdjGraph, ahu: &str) -> bool {
    select_points(g, ahu).iter().any(|p| {
        types_of(g, p).iter().any(|t| t.contains("Supply_Air_Temperature"))
    })
}
```

UNION: merge results from two predicates or two equipment branches.

## Why This Matters

Commissioning scripts ask yes/no questions before trend analysis—ASK is the RDF form.

## Mini Examples

- ASK: does AHU1 have a SAT-typed point?
- UNION: merge results from two sensor-class patterns into one list.

## Micro Exercises

1. ASK three rules on your `ahu1.ttl` model.
2. UNION query for two different sensor class patterns.
3. Print PASS/FAIL report markdown from Rust `main`.

## Key Takeaway

**Existence checks are first-class**—not everything is a SELECT table.

---

## Python companion — ASK and UNION

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# ASK/UNION mindset—implement checks in Rust on your graph.
types = {"ex:SAT": ["brick:Supply_Air_Temperature_Sensor"]}
ask_has_sat = any("Supply_Air_Temperature" in t for ts in types.values() for t in ts)
a = {"ex:SAT"}; b = {"ex:OAT"}
union_ids = a | b
print("ASK", ask_has_sat, "UNION", union_ids)
```

| Rust (main lesson) | Python |
|--------|--------|
| `ask_has_sat` / UNION merge | `any(...)` and `set \| set` |
| PASS/FAIL commissioning report | print bool + merged ids |

**Takeaway:** ASK is yes/no; UNION merges patterns—sketch with `any`/`set`, ship checks in Rust.
