## Day 58 – Reading Turtle (By Hand, Then Parse Lite)

### Goal

Read **Turtle** syntax and optionally parse a tiny file with a minimal line-based approach or **`rio_turtle`** / **`oxrdf`** crate (pick one for stretch).

### Concept

```turtle
@prefix ex: <http://example.com/bldg#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .

ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:SAT .

ex:SAT a brick:Supply_Air_Temperature_Sensor .
```

Punctuation: `.` terminates; `;` continues same subject; `,` object list.

### Why This Matters

Brick models ship as **`.ttl` files**—you must read them even if Rust code builds graphs programmatically.

### Mini examples

- Rewrite one block using full IRIs only (no prefixes).
- Count triples in a 10-line file by hand.

### Micro exercises

1. Write `mini.ttl` for one equip + one point.
2. Optional: `cargo add oxrdf` and parse `mini.ttl` in 20 lines.
3. Compare to Haystack Zinc—what's easier for humans?

### Key takeaway

**Turtle is the human-friendly RDF syntax**—Rust stores the parsed graph in memory structures from Days 57–59.
