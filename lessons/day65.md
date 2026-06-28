## Day 65 – open-fdd Drivers & Semantic Layer

### Goal

Relate **Rust drivers** (BACnet, Haystack, Modbus) in open-fdd to the graphs you build—conceptual architecture day.

### Concept

Layers:

1. **Transport** — UDP/TCP (this course Weeks 5–6)
2. **Driver** — rusty-bacnet / HTTP client / modbus crate
3. **Normalization** — point IDs, units, timestamps
4. **Semantics** — Brick/RDF tags for rules (FDD expressions)

Read: `open-fdd` workspace driver configs and commission CSVs if available locally.

### Why This Matters

You aren't learning Rust in a vacuum—you're learning **edge BAS architecture**.

### Mini examples

- Diagram: BACnet PV → internal point id → Brick class column for rule.
- List env vars that disable BACnet server on commission host (lab lesson learned).

### Micro exercises

1. Trace one point from Wireshark BACnet frame to FDD rule input name (conceptual).
2. Where would `ahu1.ttl` live in a deployment story?
3. MCP/agent prompts that reference drivers—skim open-fdd agent prompt if present.

### Key takeaway

**Network programming enables drivers; RDF enables reasoning across drivers.**
