## Day 51 — Reading Turtle: `.` `;` `,` and `@prefix`

### Goal

Read **Turtle** (Terse RDF Triple Language) well enough to **hand-debug** small Brick snippets: **period** ends a statement; **semicolon** repeats subject; **comma** repeats subject+predicate.

### Concept

```turtle
@prefix ex: <https://example.edu/bldg/> .
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:ahu1 a brick:Air_Handler_Unit ;
    brick:hasPoint ex:ahu1/sat .

ex:ahu1/sat a brick:Supply_Air_Temperature_Sensor .
```

Read line 5–6 as **two** triples sharing `ex:ahu1`.

### Why this matters

Brick distribution, **GraphDB**, **Blazegraph**, **Oxigraph** dumps, and **git** diffs of building models are mostly Turtle or TriG. Reading beats guessing.

### Mini exercises

1. Rewrite the snippet above as an **explicit** list of `(s,p,o)` tuples (no `;` or `,`).
2. What triple does `a` expand to?
3. Find one **syntax error** in a deliberately broken Turtle snippet (instructor-provided) by eye.

### Key takeaway

**Turtle sugar = shared subject/predicate.** Parsing is a machine job next lesson; **reading** is your job today.
