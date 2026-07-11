# Day 62 – Hand-Author Brick Model for One AHU

*Part VII: RDF & Brick | Week 12*

## Goal

Write **`ahu1.ttl`** by hand for one AHU, SAT, OAT, and **`brick:hasPoint`**—load and query in oxrdf and rdflib.

## Concept

Minimum entities:

- `ex:AHU1` a `brick:AHU`
- Points: SAT, OAT as sensor classes
- Optional: `ex:VAV1 brick:isFedBy ex:AHU1`

```turtle
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ex: <http://example.com/bldg#> .

ex:AHU1 a brick:AHU ;
    brick:hasPoint ex:AHU1-SAT , ex:AHU1-OAT .
ex:AHU1-SAT a brick:Supply_Air_Temperature_Sensor .
ex:AHU1-OAT a brick:Outside_Air_Temperature_Sensor .
```

**Starter file:** extend [`capstone/model/ahu1.ttl`](./capstone/model/ahu1.ttl) if present (N4 bench naming).

Load with Day 58 pattern (`oxrdfio` / `rdflib.parse`); list points with Day 59 lookup.

## Why This Matters

Commissioning deliverables increasingly include **semantic models** alongside BACnet point lists.

## Mini Examples

- Assert ≥ 8 triples after parse.
- Pretty-print subjects that are points of AHU1.

## Micro Exercises

1. At least 8 triples in the TTL file.
2. Query all `brick:hasPoint` of AHU1 in Rust and Python.
3. Screenshot Turtle + both query outputs for portfolio.

## Key Takeaway

**Small accurate models beat huge auto-generated junk**—hand authoring builds intuition.

---

## Python companion — Load & query same `ahu1.ttl`

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from rdflib import Graph, Namespace

EX = Namespace("http://example.com/bldg#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")

g = Graph()
g.parse("ahu1.ttl", format="turtle")  # same file Rust loads
points = list(g.objects(EX.AHU1, BRICK.hasPoint))
print(len(g), points)
```

| Rust (oxrdf) | Python (rdflib) |
|--------|--------|
| hand-author + `RdfParser` | `g.parse("ahu1.ttl")` |
| `triples_for_subject` / filter hasPoint | `g.objects(AHU1, hasPoint)` |
| same TTL | same |

**Takeaway:** One hand-built AHU model; both stacks load and list points.
