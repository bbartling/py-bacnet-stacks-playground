## Day 58 — The `brick:` namespace and what it defines

### Goal

Articulate what **Brick** adds on top of raw RDF: a **curated vocabulary** of **classes** (equipment, locations, points, substances, quantities…) and **relationships** tuned for buildings. Brick reuses **RDF/RDFS/OWL** machinery; you do not memorize every class.

### Concept

Official Brick publishes **OWL** + documentation. Practically:

- Class IRIs live under the Brick namespace (see current Brick release for exact IRI pattern).
- You **reuse** class IRIs in `rdf:type` triples and in **SHACL** / documentation elsewhere (SHACL optional for this course).

### Why this matters

**open-fdd** `brick:` keys in YAML inputs are **labels** that resolve, via `column_map`, to **columns**—but in a graph pipeline the same strings align with **Brick class IRIs** for discovery and SPARQL.

### Mini exercises

1. Open Brick documentation index; bookmark **three** class names you actually have on site (e.g. AHU, VAV, SAT sensor).
2. Write one sentence: difference between **Brick class** and **BACnet object type**.
3. In Turtle, assert `ex:room101 a brick:Room` (use real namespace from docs).

### Key takeaway

**Brick = building-centric vocabulary layer.** RDF is the file format; Brick names the *kinds* of things in a BAS.
