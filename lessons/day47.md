## Day 47 — Triples as tuples; a list as a toy graph

### Goal

Represent RDF **triples** as **`(subject, predicate, object)`** tuples (all `str` for now). Store many in a **`list`**. That list is your **in-memory graph** for exercises—unordered unless you sort a copy for debugging.

### Concept

Each triple is one **statement**: *subject* **predicate** *object*.

- Subject: usually an IRI (resource).
- Predicate: IRI (property / relationship type).
- Object: IRI **or** literal (later lessons add datatype).

Duplicate triples in a list are allowed in raw form; RDF **sets** treat duplicates as one—Day 57 revisits deduplication.

### How to use it

```python
triples = []
triples.append(
    (
        "https://example.edu/bldg/ahu1",
        "https://brickschema.org/schema/Brick#hasPoint",
        "https://example.edu/bldg/ahu1/sat",
    )
)
triples.append(
    (
        "https://example.edu/bldg/ahu1/sat",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
        "https://brickschema.org/schema/Brick#Supply_Air_Temperature_Sensor",
    )
)


def count_predicates(graph, predicate_iri):
    n = 0
    for s, p, o in graph:
        if p == predicate_iri:
            n += 1
    return n
```

### Why this matters

`rdflib` will iterate `(s, p, o)` the same way. Your mental model should match the library’s iterator.

### Mini exercises

1. Write `objects_for_subject(graph, subj)` returning a **list** of all `o` where `(subj, any, o)` in `graph`.
2. Write `predicates_for_subject_object(graph, subj, obj)` returning predicates linking `subj` to `obj`.
3. Add a third triple: `ahu1` **feeds** `vav101` (use IRIs you invent under `ex:`).

### Key takeaway

**Graph = collection of triples.** A Python `list` of 3-tuples is enough to practice every RDF idea until you load Turtle with `rdflib`.
