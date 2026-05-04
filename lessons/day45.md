## Day 45 — URIs and IRIs as identity strings

### Goal

Treat a **URI** / **IRI** as an **immutable identifier string**—not a file path you `open()`, though it may look like a URL. Distinguish **resource** (thing in the world or model) from **literal** (string, number, date encoded as lexical value).

### Concept

Examples (illustrative only—your site would use your own base):

- `https://example.edu/bldg/ahu1` — might identify an AHU instance.
- `https://brickschema.org/schema/Brick#Supply_Air_Temperature_Sensor` — a **class** IRI from the Brick namespace.

In Python you store these as **`str`**. Equality is string equality. **Normalization** (trailing slash, scheme, encoding) matters when merging data from two vendors.

### How to use it

```python
def same_resource(uri_a, uri_b):
    return uri_a.strip() == uri_b.strip()


AHU_A = "https://example.edu/bldg/ahu1"
AHU_B = "https://example.edu/bldg/ahu1 "
print(same_resource(AHU_A, AHU_B))  # True after strip
```

### Why this matters

RDF **never** merges rows on “column name”; it merges on **same URI** (or explicit `sameAs`). BACnet instance numbers are local; URIs are how **BMS + analytics + FDD** agree on *the same* asset across systems.

### Mini exercises

1. Given two lists of URI strings, write a loop to print URIs that appear in **both** (set intersection pattern—Day 48 preview, or double loop now).
2. Why is `http://` vs `https://` a problem if two sources mint “the same” equipment differently?
3. Look up **Brick’s published namespace** string (read-only web search or Brick docs) and write it in a variable `BRICK_NS`.

### Key takeaway

**IRIs are names.** Python holds them as strings; RDF tools resolve prefixes and compare identity with graph rules you will load later.
