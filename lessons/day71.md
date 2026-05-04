## Day 71 — Capstone: SPARQL over a small Brick model

### Goal

Combine **Weeks 7–10**: load a **small Turtle file** you author (or start from the template below), run **at least three** SPARQL queries:

1. **List** all `brick:Air_Handler_Unit` instances.
2. **List** all points related via `brick:hasPoint` to a chosen AHU (variable `?p`).
3. **`OPTIONAL`** list SAT sensors per AHU; note unbound slots.

Write **short prose** documenting what each query answers for a **commissioning tech**.

### Sample model (save as `capstone.ttl` and extend)

```turtle
@prefix ex: <https://example.edu/bldg/> .
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:ahu1 a brick:Air_Handler_Unit ;
    brick:hasPoint ex:ahu1/sat ;
    brick:hasPoint ex:ahu1/oat .

ex:ahu1/sat a brick:Supply_Air_Temperature_Sensor .
ex:ahu1/oat a brick:Outside_Air_Temperature_Sensor .
# Class IRIs: confirm against the Brick version you use in production.
```

### Starter query (extend)

```sparql
PREFIX ex: <https://example.edu/bldg/>
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?ahu ?p ?ptype
WHERE {
  ?ahu rdf:type brick:Air_Handler_Unit .
  ?ahu brick:hasPoint ?p .
  ?p rdf:type ?ptype .
}
ORDER BY ?ahu ?p
```

### Deliverables

- `capstone.ttl` (≥ your template size, with at least **two** AHUs or **one** AHU + **floor**).
- `queries.rq` or a Python script using `rdflib` that prints results for queries 1–3.
- **README fragment** (5 sentences): how you would connect these IRIs to **historian columns** for an open-fdd-style rule.

### Key takeaway

**RDF data modeling + SPARQL pattern matching** closes the loop from **Python lists** (Days 44–50, after optional maze Days 41–43) to **interoperable building graphs**—the same stack Brick tools and graph-first FDD workshops build on.
