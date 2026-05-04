## Day 59 — Equipment taxonomy (AHU, VAV, terminal units)

### Goal

Navigate **subclass** chains at a **high level**: e.g. terminal units, air handlers, chillers. You read **taxonomy** to pick the **most specific correct** `rdf:type` for commissioning data—not to memorize the whole lattice.

### Concept

Draw a **tiny** hierarchy on paper (English):

- `Air_Handler_Unit` ⊂ `HVAC_Equipment` (illustrative—verify in Brick).

In data, **subClassOf** triples come from the ontology file, not always from your site file. Your site file usually asserts **instances** with **specific** classes.

### Why this matters

Under-specifying types (`brick:Equipment` everywhere) makes **SPARQL** and **FDD rules** noisy. Over-specifying wrong types breaks **validation**.

### Mini exercises

1. List two **sibling** classes under a common parent (from Brick docs) relevant to your campus.
2. If a device is **both** packaged RTU and AHU in vendor docs, which risk do you choose when typing in Brick (under- vs over-modeling)?
3. Add `rdf:type` triples for two VAVs and one AHU in a toy `Graph`.

### Key takeaway

**Taxonomy guides typing.** Brick’s class tree is the shared language between **engineers** and **software**.
