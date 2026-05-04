## Day 46 — Adjacency list: `dict` of outgoing edges

### Goal

Store a **directed multigraph** as `dict[str, list[tuple[str, str]]]`: **subject IRI** maps to a **list** of `(predicate_iri, object_iri_or_literal_repr)` pairs. This is a classic **adjacency list**—useful for Brick-style “what hangs off this AHU?” queries before SPARQL.

### Concept

Same triples as Day 44, reorganized for fast “**all edges from this node**” lookup.

```python
def add_edge(graph, subj, pred, obj):
    if subj not in graph:
        graph[subj] = []
    graph[subj].append((pred, obj))


def neighbors(graph, subj):
    if subj not in graph:
        return []
    return list(graph[subj])  # copy
```

### Why this matters

Graph databases still answer “**outgoing edges**” and **pattern matching**. Your dict mirrors how you might **index** triples in a tiny edge service on a Pi.

### Mini exercises

1. Build `adj` from the flat `triples` list of Day 44 (one loop: `add_edge` each).
2. Write `has_edge(adj, subj, pred, obj)` returning `bool`.
3. Count distinct **subjects** that appear as **object** anywhere (two passes over data—no set comprehension: use empty dict keys as set stand-in, or introduce `set()` explicitly if allowed—**using `set()` is fine**; course avoided *comprehensions*, not `set()`).

### Key takeaway

**Same graph, many views:** list of triples vs adjacency dict. SPARQL engines use far smarter indexes—but your mental model starts here.
