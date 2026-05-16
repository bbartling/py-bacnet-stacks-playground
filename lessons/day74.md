## Day 74 — `DISTINCT`, `ORDER BY`, `LIMIT` (query hygiene)

### Goal

Make SPARQL results **stable** and **readable**: **`DISTINCT`** removes duplicate variable bindings; **`ORDER BY`** sorts on string or numeric forms; **`LIMIT`** caps rows for dashboards.

### Concept

```sparql
SELECT DISTINCT ?p
WHERE {
  ?ahu rdf:type brick:Air_Handler_Unit .
  ?ahu brick:hasPoint ?p .
}
ORDER BY ?p
LIMIT 50
```

### Why this matters

Large Brick merges return **thousands** of points. UI and notebooks need **paged** queries—same as SQL `LIMIT`.

### Mini exercises

1. Add `ORDER BY DESC(?p)` if your engine supports `DESC` on IRIs (lexical on `STR(?p)` safer).
2. Explain duplicate bindings: when can `DISTINCT` hide a **semantic** problem (same IRI, different contexts—advanced) vs a true duplicate?
3. Pull **first 5** SAT sensors only—query + print.

### Key takeaway

**DISTINCT/ORDER/LIMIT** are production SPARQL hygiene—pair them with **good variable lists** in `SELECT`.
