## Day 53 — Serialization and round-trip

### Goal

Control **ordering** only indirectly (serializers may reorder blank nodes). Practice **`graph.serialize(format="turtle")`** to bytes/str, write to `.ttl` file, **re-parse**, and compare **triple set** equality—not string equality.

### Concept

Build two graphs from two strings that **look different** but assert the same triples (use `;` in one, fully expanded in other). Use:

```python
def triple_set(graph):
    s = set()
    for tr in graph:
        s.add(tr)
    return s


g1 = Graph()
g1.parse(data=ttl_a, format="turtle")
g2 = Graph()
g2.parse(data=ttl_b, format="turtle")
print(triple_set(g1) == triple_set(g2))
```

### Why this matters

**CI pipelines** for Brick models should diff **semantics** (canonicalization tools exist in the wild); for this course, **set equality** of triples is enough intuition.

### Mini exercises

1. Serialize with `format="nt"` (N-Triples); note one triple per line—easier for `diff`.
2. Save Turtle to `model.ttl`, read back with `open(...).read()`, parse.
3. Explain why **pretty-print** order must not be used as a merge conflict resolution strategy.

### Key takeaway

**Round-trip = parse(serialize(g)) ≈ g** at triple level. Strings will differ; graphs should match.
