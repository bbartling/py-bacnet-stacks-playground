# Day 61 – Haystack Tags vs Brick Graphs

*Part VII: RDF & Brick | Week 12*

## Goal

Compare **Haystack tag dictionaries** (Zinc/CSV) with **Brick RDF graphs**—emit the same triples from a row in both stacks.

## Concept

Haystack row (conceptual):

```
id,dis,equipRef,curVal,unit
@ahu1.oa-t,"OA Temp",@ahu1,55.3,°F
```

Brick graph (target triples):

```
ex:ahu1-oa-t rdf:type brick:Outside_Air_Temperature_Sensor .
ex:ahu1 brick:hasPoint ex:ahu1-oa-t .
```

```rust
use oxrdf::{Graph, NamedNode, Triple, vocab::rdf};

fn haystack_row_to_graph(id_local: &str, equip_local: &str) -> Graph {
    let mut g = Graph::new();
    let point = NamedNode::new(format!("http://example.com/bldg#{id_local}")).unwrap();
    let equip = NamedNode::new(format!("http://example.com/bldg#{equip_local}")).unwrap();
    let ty = NamedNode::new(
        "https://brickschema.org/schema/Brick#Outside_Air_Temperature_Sensor",
    ).unwrap();
    let hp = NamedNode::new("https://brickschema.org/schema/Brick#hasPoint").unwrap();
    g.insert(Triple::new(point.clone(), rdf::TYPE, ty));
    g.insert(Triple::new(equip, hp, point));
    g
}
```

## Why This Matters

Niagara speaks Haystack; analytics ontologies speak Brick—**edge services translate**.

## Mini Examples

- Convert one golden Zinc row to 2–3 triples; serialize or print both sides.
- Tags not in Brick—optional `ex:tag` literal triples.

## Micro Exercises

1. Table: 3 things Haystack does well vs 3 things Brick does well.
2. Implement `haystack_row_to_*` returning at least the two triples above.
3. Where does rusty-haystack stop and RDF begin?

## Key Takeaway

**Tags for ops/runtime; graphs for mergeable semantics**—you need both in modern BAS stacks.

---

## Python companion — Same row → same triples

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Namespace, RDF

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

row = {"id": "ahu1-oa-t", "equipRef": "ahu1"}
g = Graph()
g.add((EX[row["id"]], RDF.type, BRICK.Outside_Air_Temperature_Sensor))
g.add((EX[row["equipRef"]], BRICK.hasPoint, EX[row["id"]]))
print(len(g))  # 2 — same as oxrdf
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| `haystack_row_to_graph` | dict row → `g.add` ×2 |
| `rdf:type` + `brick:hasPoint` | same IRIs |
| edge bridge story | same mapping shape |

**Takeaway:** Haystack rows are dicts; Brick is triples—map once, insert in both stacks.
