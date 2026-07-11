# Day 69 – FILTER & OPTIONAL Patterns in Rust

## Goal

Implement SPARQL-like **`FILTER`** (numeric compare) and **`OPTIONAL`** (maybe-missing edges) on your graph API.

## Concept

```rust
fn optional_point_label(g: &AdjGraph, pt: &str) -> Option<String> {
    let label_pred = "http://www.w3.org/2000/01/rdf-schema#label";
    objects_of(g, pt, label_pred).into_iter().next().and_then(|o| match o {
        RdfObject::Literal { lex, .. } => Some(lex.clone()),
        _ => None,
    })
}
```

FILTER: keep sensors where parsed literal > threshold.

## Why This Matters

Real models miss labels, units, or optional points—queries must not explode on absence.

## Mini Examples

- Print label or `None` when `rdfs:label` is missing.
- Keep only points whose numeric literal is above a threshold.

## Micro Exercises

1. Query all temperature sensors with optional `rdfs:label`.
2. Filter SAT > 55.0 if literal present.
3. Compare to SQL LEFT JOIN in one sentence.

## Key Takeaway

**OPTIONAL = left join mindset**—essential for commissioning-grade incomplete graphs.

---

## Python companion — `.get` and FILTER

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# OPTIONAL/FILTER intuition—query API is Rust.
points = [
    {"iri": "ex:SAT", "label": "Supply Air Temp", "val": 57.0},
    {"iri": "ex:OAT", "label": None, "val": 48.0},
]
for p in points:
    label = p.get("label") or "(no label)"  # OPTIONAL
    if p.get("val") is not None and p["val"] > 50:  # FILTER
        print(p["iri"], label, p["val"])
```

| Rust (main lesson) | Python |
|--------|--------|
| `optional_point_label` / FILTER loops | `.get` + `if val > threshold` |
| Incomplete commissioning graphs | missing keys are normal |

**Takeaway:** OPTIONAL is “maybe missing”; FILTER is “keep if”—Python `.get` mirrors the Rust query mindset.
