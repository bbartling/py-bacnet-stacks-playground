# Day 73 – Agent-Ready Point Metadata (JSON)

*Week 9 · Live data → graph · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Query the Brick graph, then emit **JSON / NDJSON** point rows for MCP/agents—same SELECT intent, two serializers.

## Concept

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ex:    <http://example.org/>
SELECT ?p ?v WHERE {
  ex:AHU1 brick:hasPoint ?p .
  OPTIONAL { ?p rdf:value ?v }
}
```

Shape each row: `iri`, `brick_class`, `cur_val`, `bacnet_ref` (Day 53). Rust: `serde_json`; Python: `json.dumps`.

## Why This Matters

Agents speak **JSON** first—RDF supplies context; JSON is the tool API.

## Mini Examples

- One JSON line per temperature sensor.
- Include `bacnet_ref` from your map.

## Micro Exercises

1. Rust: `cargo add serde serde_json`; Python: stdlib `json`.
2. Emit `points.ndjson` from the SELECT above (both stacks).
3. Validate with `jq .` per line.

## Key Takeaway

**Agents don't speak SPARQL first—they speak JSON**—serve both graph and tool APIs.

---

## Python companion — SELECT → NDJSON

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
import json
from rdflib import Graph

g = Graph()
g.parse("lessons/capstone/model/ahu1.ttl", format="turtle")  # adjust path
q = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ex: <http://example.org/>
SELECT ?p ?v WHERE {
  ex:AHU1 brick:hasPoint ?p .
  OPTIONAL { ?p rdf:value ?v }
}
"""
for row in g.query(q):
    print(json.dumps({"iri": str(row.p), "cur_val": float(row.v) if row.v else None,
                       "bacnet_ref": "AI:1"}))
```

| Rust (`oxrdf` + `serde_json`) | Python (`rdflib` + `json`) |
|--------|--------|
| Same SELECT → NDJSON | Same query → `json.dumps` |
| Agent file export | Same row shape |

**Takeaway:** One query, JSON rows—graph in, tool API out.
