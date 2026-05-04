## Day 43 — Prefix maps: expand `brick:Thing` by hand

### Goal

Build a **`dict`** mapping **prefix** (without colon) to **namespace base** IRI, then write `expand(prefixed_name)` that turns `brick:Supply_Air_Temperature_Sensor` into a full string—same job Turtle `@prefix` does.

### Concept

Turtle / SPARQL allow **QName** shorthand: `prefix:LocalName`. The parser **expands** to `namespace_base + LocalName` (with rules for fragments `#` vs `/`—your lesson code can assume the base already ends with `#` or `/` as given).

### How to use it

```python
def expand(prefix_map, qname):
    """qname like 'brick:Supply_Air_Temperature_Sensor'."""
    if ":" not in qname:
        return qname
    prefix, local = qname.split(":", 1)
    if prefix not in prefix_map:
        raise KeyError("unknown prefix: " + prefix)
    return prefix_map[prefix] + local


PREFIXES = {
    "brick": "https://brickschema.org/schema/Brick#",
    "ex": "https://example.edu/bldg/",
}

print(expand(PREFIXES, "ex:ahu1"))
```

### Why this matters

Every RDF file and SPARQL query relies on **prefix expansion**. Doing it once manually demystifies `@prefix` lines and `PREFIX` blocks.

### Mini exercises

1. Add `rdf`, `rdfs` entries using common W3C namespace IRIs (look up once, paste as constants).
2. Write `shorten(full_uri, prefix_map)` that returns a QName if `full_uri` starts with one known base; else return `full_uri` unchanged (linear scan over `items()`).
3. What breaks if `local` contains an extra `:`?

### Key takeaway

**Prefix map = Python `dict`.** Expansion is string concatenation with rules you control in small code—same idea as Turtle.
