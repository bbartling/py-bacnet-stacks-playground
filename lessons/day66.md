# Day 66 – Serialize Graph to Turtle from Rust

## Goal

Write **`graph.serialize_turtle()`**—emit prefixes and triples from your adjacency structure.

## Concept

```rust
impl AdjGraph {
    fn to_turtle(&self, prefix_map: &HashMap<&str, &str>) -> String {
        let mut out = String::new();
        for (pfx, iri) in prefix_map {
            out.push_str(&format!("@prefix {pfx}: <{iri}> .\n"));
        }
        // emit "subj pred obj ." lines — simplify IRIs with prefixes when possible
        out
    }
}
```

Round-trip: TTL → graph → TTL should preserve triple count.

## Why This Matters

Exporting models for **Brick validation tools** and partners requires serialization—not only in-memory graphs.

## Mini Examples

- Round-trip `ahu1.ttl` through parse (if using oxrdf) and your serializer.
- Git-diff two exports—stable sort lines for clean diffs.

## Micro Exercises

1. Serialize Day 62 model from code-built graph.
2. Handle literal datatypes in output `^^xsd:double`.
3. Unit test: parse count == serialize count.

## Key Takeaway

**RDF interoperability is file exchange**—Turtle generation completes the Rust RDF mini-stack.

---

## Python companion — Emit Turtle lines

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# String join sketch—course serializer is Rust `to_turtle`.
triples = [("ex:AHU1", "a", "brick:AHU"), ("ex:AHU1", "brick:hasPoint", "ex:SAT")]
lines = ["@prefix brick: <https://brickschema.org/schema/Brick#> ."]
lines += [f"{s} {p} {o} ." for s, p, o in triples]
print("\n".join(lines))
```

| Rust (main lesson) | Python |
|--------|--------|
| `AdjGraph::to_turtle` + round-trip | `"\\n".join(...)` of triple strings |
| Prefix map + IRI shorten | hard-coded prefixes for intuition |

**Takeaway:** Serialization is formatting triples as text—practice in Python; complete the mini-stack in Rust.
