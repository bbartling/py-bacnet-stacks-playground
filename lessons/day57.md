## Day 54 — Merging graphs and deduplicating triples

### Goal

Parse **two** Turtle snippets into `g1` and `g2`, **`g1 += g2`** (or `graph1 += graph2` in rdflib), then reason about **duplicates**. Practice converting to a **Python `set`** of **frozen** triple representations only if hashable—`rdflib` terms are not always trivially hashable in older patterns, so use: **“add all triples from g2 into g1 and trust rdflib”** + **count** before/after.

### Concept

```python
from rdflib import Graph

g_merged = Graph()
g_merged.parse(data=ttl_site, format="turtle")
g_merged.parse(data=ttl_vendor_addon, format="turtle")
```

If the same triple appears twice, RDF set semantics treat it as one **edge**. `rdflib` `Graph` is **like a set of triples** for addition.

### Why this matters

**Site model + vendor asset pack + FDD ontology slice** = merge in memory or store in triplestore. Conflicts are **same subject/predicate, different object**—resolution is policy, not syntax.

### Mini exercises

1. Merge a graph that asserts `ex:ahu1 brick:hasPoint ex:p1` with another that asserts the same triple—did `len` change?
2. Merge graphs that **conflict** on `ex:ahu1 ex:commissionedOn` object—list both objects after merge (rdflib keeps both unless you remove—observe behavior).
3. Write English **policy** rules for resolving commissioning date conflicts (no code).

### Key takeaway

**Merge = union of assertions.** Duplicates vanish; **conflicts** need human or rule-based resolution outside raw RDF.
