## Day 52 — `rdf:type` and class hierarchies (`rdfs:subClassOf`)

### Goal

Read **instance typing**: `ex:ahu1 rdf:type brick:Air_Handler_Unit`. Read **taxonomy**: `brick:VAV rdfs:subClassOf brick:Terminal_Unit` (examples illustrative—verify current Brick class names in official Brick for production).

### Concept

- **`rdf:type`**: “this individual is a member of that class.”
- **`rdfs:subClassOf`**: “every A is a B” for reasoning; not the same as `rdf:type`.

In Python triple lists, these are just **more rows** with well-known predicate IRIs:

```python
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
```

### Why this matters

SPARQL `FILTER` and **RDFS inference** (in engines that support it) use these predicates. Even without a reasoner, **you** manually assert enough `rdf:type` rows for queries to work.

### Mini exercises

1. Add triples: `vav101` `rdf:type` `brick:VAV` (use full IRIs you control).
2. Explain: if `brick:VAV` is subclass of `brick:Terminal_Unit`, does your data **need** both type triples? When might you add both anyway?
3. Find Brick’s **namespace** and one **AHU** class IRI from official docs; paste into a comment in a `.py` file.

### Key takeaway

**Taxonomies = extra triples** using `rdfs:subClassOf`. **Instances** use `rdf:type`. SPARQL will ask both kinds of questions.
