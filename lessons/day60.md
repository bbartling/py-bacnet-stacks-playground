## Day 60 — FDD inputs and Brick class names (open-fdd bridge)

### Goal

Connect **open-fdd** style **`inputs`** blocks (logical names + optional `brick:` hints) to **ontology**: the **string** after `brick:` in YAML is meant to align with **Brick class** IRIs for that concept—not arbitrary prose.

### Concept

Read one recipe from **`open-fdd/docs/expression_rule_cookbook.md`** (local clone). List each **input** key and its **Brick** field. In Python, model that as `dict` mapping **logical name** → **Brick class IRI string** (column mapping to historian columns stays separate).

### Why this matters

Same idea as **223P** / **DBO** fields in that cookbook: **first match wins** resolvers—the **advanced data structure** is the **resolver chain**, but you implement a **single dict** first (`logical_name -> column_name`) before learning priority composites.

### Mini exercises

1. For Rule A (duct static), list **inputs** and which are **sensors** vs **setpoints** vs **commands**.
2. Write a Python `dict` `logical_to_brick_class` with two entries from that rule.
3. Explain how a **SPARQL** query could later list “all points typed as this Brick class on this AHU”—preview Day 68.

### Key takeaway

**FDD rules consume logical columns; ontologies name the semantics.** Brick IRIs are the bridge vocabulary.
