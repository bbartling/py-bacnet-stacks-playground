## Day 70 — `FILTER` and `BIND` (numbers and computed values)

### Goal

Narrow results with **`FILTER` expressions** and create **computed columns** with **`BIND`**—e.g. only points whose **numeric literal** (if modeled) passes a test. For this course, **`FILTER`** on **IRIs** or **regex on string form** is enough if you did not add `xsd:decimal` literals.

### Concept

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?p
WHERE {
  ?p rdf:type brick:Supply_Air_Temperature_Sensor .
  FILTER ( STRSTARTS( STR(?p), "https://example.edu/bldg/ahu1" ) )
}
```

(`STRSTARTS` availability depends on SPARQL engine; `rdflib` supports much of SPARQL 1.1—if a function fails, fall back to **Python post-filter** on query results for 101.)

### Why this matters

**FDD** thresholds on **trend data** live in Pandas in open-fdd; in **ontology land**, you filter **metadata** (“sensors on this AHU only”) before joining to historians.

### Mini exercises

1. Write `FILTER ( ?p != <https://example.edu/bldg/ahu1/oat> )` style inequality on two IRIs you know.
2. `BIND` a boolean `?is_sat` using `CONTAINS` or `regex` on `STR(?p)`—optional if your engine supports those functions.
3. If `rdflib` rejects a function, filter results in Python with a `for` loop—same outcome.

### Key takeaway

**FILTER/BIND = SQL HAVING/SELECT expressions** at the graph-pattern layer—useful for **metadata slicing**.
