# Day 65 – open-fdd Drivers & Semantic Layer

## Goal

Relate **Rust drivers** (BACnet, Haystack, Modbus) in open-fdd to the graphs you build—conceptual architecture day.

## Concept

Layers:

1. **Transport** — UDP/TCP (this course Weeks 5–6)
2. **Driver** — rusty-bacnet / HTTP client / modbus crate
3. **Normalization** — point IDs, units, timestamps
4. **Semantics** — Brick/RDF tags for rules (FDD expressions)

Read: `open-fdd` workspace driver configs and commission CSVs if available locally.

## Why This Matters

You aren't learning Rust in a vacuum—you're learning **edge BAS architecture**.

## Mini Examples

- Diagram: BACnet PV → internal point id → Brick class column for rule.
- List env vars that disable BACnet server on commission host (lab lesson learned).

## Micro Exercises

1. Trace one point from Wireshark BACnet frame to FDD rule input name (conceptual).
2. Where would `ahu1.ttl` live in a deployment story?
3. MCP/agent prompts that reference drivers—skim open-fdd agent prompt if present.

## Key Takeaway

**Network programming enables drivers; RDF enables reasoning across drivers.**

---

## Python companion — Layer stack sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Architecture notes—drivers/graphs are the Rust track.
stack = {
    "transport": "UDP/TCP",
    "driver": "bacnet | haystack | modbus",
    "normalize": "point id, unit, ts",
    "semantics": "Brick/RDF for FDD rules",
}
for layer, role in stack.items():
    print(f"{layer}: {role}")
```

| Rust (main lesson) | Python |
|--------|--------|
| open-fdd-style drivers + RDF | nested dict of layer names |
| Wire → point → Brick class | same story as labels only |

**Takeaway:** Python sketches the architecture; Rust owns transport, drivers, and the semantic graph.
