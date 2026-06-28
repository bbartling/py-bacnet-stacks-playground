## Day 70 – UNION & ASK Queries

### Goal

Implement **`UNION`** (two patterns, merge results) and **`ASK`** (exists?) for commissioning checks.

### Concept

ASK example: "Does AHU1 have any Supply Air Temperature sensor?"

```rust
fn ask_has_sat(g: &AdjGraph, ahu: &str) -> bool {
    select_points(g, ahu).iter().any(|p| {
        types_of(g, p).iter().any(|t| t.contains("Supply_Air_Temperature"))
    })
}
```

UNION: merge results from two predicates or two equipment branches.

### Why This Matters

Commissioning scripts ask yes/no questions before trend analysis—ASK is the RDF form.

### Micro exercises

1. ASK three rules on your `ahu1.ttl` model.
2. UNION query for two different sensor class patterns.
3. Print PASS/FAIL report markdown from Rust `main`.

### Key takeaway

**Existence checks are first-class**—not everything is a SELECT table.
