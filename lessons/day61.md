## Day 61 — Hand-author a tiny Brick TTL model

### Goal

Write **20–40 lines** of Turtle (in a `.ttl` file) describing:

- one **AHU** instance,
- one **SAT** sensor instance,
- `rdf:type` for each,
- `brick:hasPoint` from AHU to sensor.

Validate by **parsing with `rdflib`** and printing triple count.

### Concept

Use `@prefix` for `ex`, `brick`, `rdf`. Use `a` for `rdf:type`. Keep **IRIs stable** and **human-readable** local names after `#` or final `/`.

### Why this matters

**Authoring** is how you learn syntax muscle memory before generators do it for you.

### Mini exercises

1. Add `ex:floor3` as a `brick:Floor` and `brick:isPartOf` from AHU to floor (if predicate fits your reading).
2. Add **labels** using `rdfs:label` if you looked up `rdfs:` prefix—optional stretch.
3. Break Turtle on purpose (missing period); confirm parser error message is readable.

### Key takeaway

**Small correct models > large wrong models.** This file becomes SPARQL homework input.
