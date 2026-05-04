## Day 51 — RDF triple model (formal one-liner)

### Goal

State RDF’s core unit: **triple** \((s, p, o)\). **Subject** and **predicate** are IRIs (or blank nodes in advanced cases—here: skip blank nodes except “sometimes object is anonymous” as a footnote). **Object** is IRI **or** literal.

### Concept

- **No duplicate meaning:** two identical triples merge to one in a **set** semantics.
- **Open world:** absence of a triple does not mean false—important for **FDD** (you query what is asserted).

### How to use it

Revisit your `list` of triples from Day 47. Classify each `o`:

- If `o` starts with `http` and matches resource naming → **resource**.
- Else if `o` is your `(lexical, datatype)` tuple → **literal**.

Write `triple_kind(s, p, o)` returning `"r-r-r"` or `"r-r-l"` as three letters.

### Why this matters

Brick files are RDF. **open-fdd** column maps name columns that *align* with Brick class IRIs—those names resolve to the same **predicate/object patterns** you practice in Python lists.

### Mini exercises

1. Give one example triple where **subject** is a **VAV** instance and **predicate** is `rdf:type`.
2. Why can two different URIs denote the “same” chiller in the real world (conceptual: `owl:sameAs`—no OWL deep dive required)?
3. List two triples that should **not** be inferred just because a sensor exists on an AHU (open-world caution).

### Key takeaway

**RDF = labeled directed multigraph expressed as triples.** Your Python tuples already *are* RDF data at the logical level.
