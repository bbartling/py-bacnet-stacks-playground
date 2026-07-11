# Day 73 – Agent-Ready Point Metadata (Rust Structs → JSON)

## Goal

Serialize query results as **JSON** for MCP/agents—network + semantics course meets AI edge workflows.

## Concept

```rust
#[derive(serde::Serialize)]
struct PointRow {
    iri: String,
    brick_class: String,
    cur_val: Option<f64>,
    bacnet_ref: Option<String>,
}
```

Use `serde_json` to emit NDJSON for agent consumption.

## Why This Matters

open-fdd agent prompts reference **driver health + point context**—JSON bridges RDF graphs to LLM tools.

## Mini Examples

- One JSON line per temperature sensor after graph query.
- Include `bacnet_ref` from Day 53 map.

## Micro Exercises

1. `cargo add serde serde_json`.
2. Emit file `points.ndjson` from combined pipeline stub.
3. Validate JSON with `jq .` per line.

## Key Takeaway

**Agents don't speak SPARQL first—they speak JSON**—Rust serves both graph and tool APIs.

---

## Python companion — Point row → JSON

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
import json
row = {"iri": "ex:AHU1-SAT", "brick_class": "Supply_Air_Temperature_Sensor",
       "cur_val": 57.2, "bacnet_ref": "AI:1"}
print(json.dumps(row))  # NDJSON = one dumps per line; Rust uses serde_json
```

| Rust (main lesson) | Python |
|--------|--------|
| `serde` `PointRow` → NDJSON | `json.dumps` dict |
| Graph query → agent file | parallel shape only |

**Takeaway:** Agents want JSON rows—Python `json` shows the shape; Rust `serde_json` is the course path.
