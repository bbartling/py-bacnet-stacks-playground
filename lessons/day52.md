## Day 52 — Literals: lexical value + datatype IRI

### Goal

Model **RDF literals** in Python without a full RDF library: store **`(lexical_string, datatype_iri_or_none)`** as the **object** side when the object is not a resource URI. Compare to **plain string object** mistakes ( `"72.5"` vs float semantics).

### Concept

RDF 1.1 literals have:

- **Lexical form** (characters), e.g. `"22.1"`.
- **Datatype** IRI, often `http://www.w3.org/2001/XMLSchema#decimal` for numbers.

In tiny exercises you may keep `object` as a single string `"22.1^^http://www.w3.org/2001/XMLSchema#decimal"` with a **documented convention**, or use a **tuple** as above—pick one style for your own code and stay consistent.

### How to use it

```python
XSD_DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"


def literal_decimal(lexical):
    return (lexical, XSD_DECIMAL)


def parse_if_decimal(lit):
    if isinstance(lit, tuple) and lit[1] == XSD_DECIMAL:
        return float(lit[0])
    return None
```

### Why this matters

Brick + timeseries integrations attach **numeric readings** to **sensor resources**; the *reading* is often a literal with a datatype, while the *sensor* is a URI. Mixing them up causes subtle export bugs.

### Mini exercises

1. Add a triple: `ex:ahu1/sat` has **present value** literal `"55.2"` as `xsd:decimal` using your tuple convention.
2. Write `is_resource_object(obj)` returning `True` if `obj` is a `str` starting with `http` and **not** your literal tuple form.
3. Why is storing a temperature as a bare Python `float` in a triple list **not** the same as an RDF typed literal (hint: JSON vs RDF graph interchange)?

### Key takeaway

**Literals carry type.** RDF cares; Python `float` is only your runtime convenience after you **parse** the lexical form.
