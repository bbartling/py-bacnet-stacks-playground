## Day 73 – Agent-Ready Point Metadata (Rust Structs → JSON)

### Goal

Serialize query results as **JSON** for MCP/agents—network + semantics course meets AI edge workflows.

### Concept

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

### Why This Matters

open-fdd agent prompts reference **driver health + point context**—JSON bridges RDF graphs to LLM tools.

### Mini examples

- One JSON line per temperature sensor after graph query.
- Include `bacnet_ref` from Day 53 map.

### Micro exercises

1. `cargo add serde serde_json`.
2. Emit file `points.ndjson` from combined pipeline stub.
3. Validate JSON with `jq .` per line.

### Key takeaway

**Agents don't speak SPARQL first—they speak JSON**—Rust serves both graph and tool APIs.
