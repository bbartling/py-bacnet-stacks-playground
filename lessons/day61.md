## Day 61 – Haystack Tags vs Brick Graphs

### Goal

Compare **Haystack tag dictionaries** (Zinc/CSV) with **Brick RDF graphs**—when to use which on projects.

### Concept

Haystack row (conceptual):

```
id,dis,equipRef,curVal,unit
@ahu1.oa-t,"OA Temp",@ahu1,55.3,°F
```

Brick graph:

```
ex:ahu1-oat rdf:type brick:Outside_Air_Temperature_Sensor .
ex:ahu1 brick:hasPoint ex:ahu1-oat .
```

Rust bridge:

```rust
fn haystack_row_to_triples(id: &str, equip: &str) -> Vec<Triple> {
    // emit rdf:type and brick:hasPoint triples — simplified lab
    vec![]
}
```

### Why This Matters

Niagara speaks Haystack; analytics ontologies speak Brick—**edge Rust services translate**.

### Mini examples

- Convert one golden Zinc row to 2–3 triples.
- Tags not in Brick—store as `ex:tag "key" "value"` literal triples optional.

### Micro exercises

1. Table: 3 things Haystack does well vs 3 things Brick does well.
2. Implement stub `haystack_row_to_triples` returning at least one triple.
3. Where does rusty-haystack stop and RDF begin?

### Key takeaway

**Tags for ops/runtime; graphs for mergeable semantics**—you need both in modern BAS stacks.
