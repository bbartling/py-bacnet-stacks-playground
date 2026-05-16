## Day 71 — `OPTIONAL` (missing points, partial models)

### Goal

Use **`OPTIONAL { ... }`** so rows still return when a **nested fact** is absent—e.g. every AHU with an **optional** `brick:hasPoint` to an OAT sensor.

### Concept

```sparql
SELECT ?ahu ?oat
WHERE {
  ?ahu rdf:type brick:Air_Handler_Unit .
  OPTIONAL { ?ahu brick:hasPoint ?oat .
             ?oat rdf:type brick:Outside_Air_Temperature_Sensor . }
}
```

If no OAT exists, `?oat` is **unbound** but `?ahu` still appears (SPARQL semantics).

### Why this matters

Real campuses ship **partial** Brick. **OPTIONAL** prevents queries from silently dropping whole equipment lines.

### Mini exercises

1. Run OPTIONAL query on your toy model; remove OAT triples and compare result rows.
2. In Python after `query`, detect unbound `None` cells in `rdflib` rows (print `row` objects).
3. When would **forbidden OPTIONAL** be better as a **separate validation query** instead?

### Key takeaway

**OPTIONAL = outer join** intuition for graph people. Use it for **commissioning completeness** checks.
