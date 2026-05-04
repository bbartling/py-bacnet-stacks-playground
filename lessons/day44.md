## Day 44 — Buildings as graphs, not only tables

### Goal

See why **smart-building digital twins** and **ontology pipelines** (Brick, Haystack+TTL, 223P) use **graphs**: things (equipment, spaces, sensors) as **nodes**, relationships as **edges**. Tables (CSV, SQL rows) are still useful—graphs add **mergeable, global identity** for data integration.

### Concept

If you tried the **optional maze block (Days 41–43)**, you already practiced **local adjacency** on a grid (four neighbors, visited flags). **Brick graphs** are the same *idea* at a different scale: named things and typed links instead of `(row, col)` and open walls.

A **graph** here means: **vertices** (things) and **edges** (relationships with a direction and a label). A BACnet device list is often a **table**. A Brick model says: *this AHU* **hasPoint** *that SAT sensor* **feeds** *that VAV*—relationships matter as much as columns.

You will not implement Dijkstra or max-flow. You will learn to **hold graph-shaped data** in Python using only structures you already know (lists, dicts, tuples, strings).

### Why this matters

Tools like **open-fdd** column maps, **Brick** SPARQL endpoints, and **AFDD** graph workshops all assume you are comfortable reading **subject–predicate–object** statements. This week builds that comfort from Python outward.

### Mini exercises

1. List three relationships in a real AHU (physical or controls) that are awkward to store in **one** flat CSV row without duplication.
2. Draw (on paper) four boxes: `AHU`, `SAT sensor`, `VAV`, `Zone`. Draw arrows labeled `hasPoint`, `feeds`, `serves`.
3. In one sentence: what does **global identity** (a URI) buy you when merging two vendor exports?

### Key takeaway

**RDF** is a *data model* for graphs. **Brick** is an **ontology** (vocabulary + expectations) on top of RDF for buildings. The next days give you Python shapes that mirror RDF without skipping your foundations.
