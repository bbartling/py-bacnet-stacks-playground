## Day 68 — `UNION` (alternative shapes)

### Goal

Combine **two graph patterns** with **`UNION`** when equipment might satisfy **either** layout—e.g. SAT under AHU **or** under a downstream assembly (toy example).

### Concept

```sparql
SELECT ?temp_sensor
WHERE {
  { ?ahu rdf:type brick:Air_Handler_Unit .
    ?ahu brick:hasPoint ?temp_sensor .
    ?temp_sensor rdf:type brick:Supply_Air_Temperature_Sensor . }
  UNION
  { ?vav rdf:type brick:Variable_Air_Volume_Box .
    ?vav brick:hasPoint ?temp_sensor .
    ?temp_sensor rdf:type brick:Supply_Air_Temperature_Sensor . }
}
```

(Use class IRIs that exist in **your** Brick release; VAV class name may differ—consult Brick docs.)

### Why this matters

**Vendor diversity** means the same **semantic** sensor appears under different parents. `UNION` collects both without forcing one false `OPTIONAL` chain.

### Mini exercises

1. Draw two small graphs that differ only in parent equipment; confirm `UNION` returns both sensors.
2. Could two branches of `UNION` **double-count** the same sensor? When?
3. Rewrite (conceptually) `UNION` as two queries + Python `set` merge—when is that acceptable offline?

### Key takeaway

**UNION = OR over patterns.** Use sparingly; document why both branches exist.
