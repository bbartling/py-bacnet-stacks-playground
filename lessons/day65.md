# Day 65 – Drivers & Semantic Layer Stack

*Part VII: RDF & Brick | Week 12*

## Goal

Relate **drivers** (BACnet, Haystack, Modbus) to the graphs you build—architecture day with a light dual-stack sketch.

## Concept

Layers:

1. **Transport** — UDP/TCP (Weeks 5–6)
2. **Driver** — rusty-bacnet / HTTP client / modbus crate
3. **Normalization** — point IDs, units, timestamps
4. **Semantics** — Brick/RDF (`oxrdf` / `rdflib`) for rules (FDD)

```rust
// Conceptual — where ahu1.ttl sits in the stack
const STACK: &[&str] = &[
    "transport: UDP/TCP",
    "driver: bacnet | haystack | modbus",
    "normalize: point id, unit, ts",
    "semantics: Brick/RDF (oxrdf Graph / mini.ttl)",
];
fn main() {
    for layer in STACK {
        println!("{layer}");
    }
}
```

Read: `open-fdd` workspace driver configs and commission CSVs if available locally.

## Why This Matters

You aren't learning Rust in a vacuum—you're learning **edge BAS architecture**.

## Mini Examples

- Diagram: BACnet PV → internal point id → Brick class for a rule.
- List env vars that disable BACnet server on the commission host.

## Micro Exercises

1. Trace one point from Wireshark BACnet frame to FDD rule input (conceptual).
2. Where would `ahu1.ttl` / `mini.ttl` live in a deployment story?
3. Skim open-fdd agent prompts that reference drivers if present.

## Key Takeaway

**Network programming enables drivers; RDF enables reasoning across drivers.**

---

## Python companion — Same layer stack

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
stack = {
    "transport": "UDP/TCP",
    "driver": "bacnet | haystack | modbus",
    "normalize": "point id, unit, ts",
    "semantics": "Brick/RDF (rdflib Graph / mini.ttl)",
}
for layer, role in stack.items():
    print(f"{layer}: {role}")
# Same story as Rust — semantics = shared Turtle + SPARQL days
```

| Rust (oxrdf track) | Python (rdflib track) |
|--------|--------|
| drivers + `oxrdf` semantics | same four layers; `rdflib` at top |
| `mini.ttl` / `ahu1.ttl` | same files |
| wire → point → Brick class | same labels |

**Takeaway:** Both stacks share the semantic top—Turtle and queries from Days 58–63 sit above the drivers.
