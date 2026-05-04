## Day 66 — `ASK` (yes/no commissioning checks)

### Goal

Use **`ASK WHERE { ... }`** to return **true/false**: “Does this graph contain **any** match?” Example: “Is there **any** AHU without a SAT point?” (pattern requires careful negation—introduce **`NOT EXISTS`** lightly or do two-step: count in SELECT for 101).

### Concept

Simple `ASK`:

```sparql
ASK {
  <https://example.edu/bldg/ahu1> rdf:type brick:Air_Handler_Unit .
}
```

In `rdflib`, **`ASK`** results expose a boolean (exact attribute varies by version—see `rdflib` SPARQL result docs). If that is fiddly in your environment, use **`SELECT (COUNT(?x) AS ?n)`** and check `n > 0` in Python instead—the logic is the same for commissioning checks.

### Why this matters

**CI gates:** fail build if **must-have** relationships are missing—`ASK` / `COUNT` queries are typical.

### Mini exercises

1. Write `ASK` for “graph contains at least one `brick:Supply_Air_Temperature_Sensor`.”
2. Convert the same check to `SELECT (COUNT(?s) AS ?n)` and treat `n>0` in Python.
3. Name one **ASK** query you would run before attaching a historian column map.

### Key takeaway

**Boolean graph questions** power automation. `ASK` is the SPARQL-native spelling.
