## Day 50 — From flat rows to nested equipment records

### Goal

**Bridge** BACnet/CSV thinking to graph prep: given **rows** as `list` of `dict` (keys like `device`, `point_name`, `brick_class`), build a **nested dict**: `equipment_id -> { "class": ..., "points": [ ... ] }` using only loops—same grouping you would need before emitting Turtle.

### Concept

Many exports are **relational**. Brick wants **things and links**. Grouping rows **by equipment** is an algorithm you already know (counting pattern with dict of lists).

```python
def group_points_by_equipment(rows):
    out = {}
    for row in rows:
        eq = row["equipment_id"]
        if eq not in out:
            out[eq] = []
        out[eq].append(row)
    return out
```

### Why this matters

Real pipelines **normalize** tabular BACnet discovery into **entities** before `owl:sameAs` / Brick typing. This step is pure Python **data structuring**—no RDF parser required.

### Mini exercises

1. Extend grouping so each equipment node also stores `row["equip_type"]` once (first-seen wins).
2. Emit a **sorted** list of equipment IDs for stable Turtle output (`sorted(out.keys())`).
3. List one **relationship** you cannot represent in one grouped dict without adding a second pass (e.g. `feeds` between two equipment IDs).

### Key takeaway

**Nested dicts + sorted keys** = human-readable, diff-friendly RDF generation later. You are now “shaping” data the way ontology tooling expects.
