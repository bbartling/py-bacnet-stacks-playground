## Day 60 — Key Brick predicates (`hasPoint`, `isPartOf`, `feeds`)

### Goal

Memorize **meanings**, not every predicate in Brick: **`brick:hasPoint`** links equipment (or space) to a **point**; **`brick:isPartOf`** composes systems; **`brick:feeds`** suggests **upstream/downstream** airflow or hydronic flow context (read Brick definitions for precise semantics).

### Concept

Represent in Python as normal predicate IRIs in triples:

```python
HAS_POINT = "https://brickschema.org/schema/Brick#hasPoint"
IS_PART_OF = "https://brickschema.org/schema/Brick#isPartOf"
FEEDS = "https://brickschema.org/schema/Brick#feeds"
```

### Why this matters

**Graph traversals** for “all SAT sensors on AHUs that feed this corridor” are **multi-hop patterns**—exactly SPARQL’s strength next week.

### Mini exercises

1. Assert: `ex:ahu1` **hasPoint** `ex:ahu1/sat`; `ex:vav12` **isPartOf** `ex:floor3`; `ex:ahu1` **feeds** `ex:vav12` (if `feeds` applies in your reading of Brick—if not, replace with a predicate your instructor approves).
2. Write `points_of(graph, equipment_iri)` returning a list of point IRIs using loops over triples.
3. What is the **direction** of `feeds` (who is subject)? Quote Brick’s English gloss.

### Key takeaway

**Predicates are verbs.** Brick picks verbs that match how **MEP** engineers already talk—then machines can query them.
