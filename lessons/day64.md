## Day 64 — Why SPARQL for smart-building graphs

### Goal

Define **SPARQL** as a **query language for RDF**: you describe a **graph pattern**; the engine returns **bindings** for variables that **match** the pattern in the dataset (in-memory `rdflib` graph or remote endpoint).

### Concept

Core shape:

```text
SELECT ?variable
WHERE {
  ?subject ?predicate ?object .
}
```

**WHERE** is not “SQL where clause” first—think **pattern match** on triples.

### Why this matters

**Commissioning queries:** “Every `Supply_Air_Temperature_Sensor` that **has** location in **this** wing.” **FDD prep:** “All AHUs without an **outside air flow** point.” These are multi-hop patterns—awkward in CSV, natural in SPARQL.

### Mini exercises

1. In English, translate: “Find all subjects `?e` such that `?e rdf:type brick:Air_Handler_Unit`.”
2. List two reasons a **triplestore** might be used instead of only files on disk.
3. Install / verify `rdflib` and read `help(Graph.query)` one screen.

### Key takeaway

**SPARQL = patterns + variables.** Next days add `FILTER`, `OPTIONAL`, `UNION`, and hygiene keywords.
