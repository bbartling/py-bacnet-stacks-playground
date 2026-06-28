## Day 62 – Hand-Author Brick Model for One AHU

### Goal

Write **`ahu1.ttl`** by hand for one AHU, SAT, OAT, and **`brick:hasPoint` / `brick:feeds`** (if applicable).

### Concept

Minimum entities:

- `ex:AHU1` a `brick:AHU`
- Points: SAT, OAT as appropriate sensor classes
- Optional: `ex:VAV1 brick:isFedBy ex:AHU1` if in scope

Load into Day 59 graph; verify counts.

**Starter file:** extend [`capstone/model/ahu1.ttl`](./capstone/model/ahu1.ttl) (N4 `v4Fifteen` bench naming).

### Why This Matters

Commissioning deliverables increasingly include **semantic models** alongside BACnet point lists.

### Mini examples

- Validate Turtle with online parser or `oxrdf` load.
- Pretty-print via your Display impl.

### Micro exercises

1. At least 8 triples in TTL file.
2. Query all points of AHU1 from Rust graph code.
3. Screenshot Turtle + Rust query output for portfolio.

### Key takeaway

**Small accurate models beat huge auto-generated junk**—hand authoring builds intuition.
