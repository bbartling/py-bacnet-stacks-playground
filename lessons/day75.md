# Day 75 – Final Capstone: Multi-Protocol Semantic Snapshot

*Week 10 · Course synthesis · Rust main (`oxrdf`) + Python companion (`rdflib`)*

## Goal

Deliver **[`capstone/`](./capstone/)** with:

1. **`discover-and-poll/`** — Rust BACnet CLI ([Day 46 starter](./capstone/discover-and-poll/))
2. **`niagara-read`** — Haystack CLI via [nhaystack-niagara-pi-tutorial](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) ([pointer](./capstone/niagara-read/README.md))
3. **`model/ahu1.ttl`** — Brick hand model ([starter](./capstone/model/ahu1.ttl))
4. **`graph-export/`** — Rust binary: hand TTL + **`oxrdf`** load (+ optional BACnet merge) → Turtle ([starter](./capstone/graph-export/))
5. **`pcaps/README.md`** — three filters on one multi-protocol capture ([template](./capstone/pcaps/README.md))
6. **`COURSE_REVIEW.md`** ([template](./capstone/COURSE_REVIEW.md))

## Concept

| Artifact | Pass criteria |
|----------|---------------|
| BACnet CLI | Reads device 5007 without panic; logs errors |
| Haystack CLI | Basic auth works; prints Zinc or parsed rows |
| TTL model | ≥8 triples; valid Turtle |
| Graph export | `oxrdf` load/round-trip triple count ≥ original |
| PCAP doc | Shows BACnet + HTTPS + filter strings |
| Python check | `pathlib` checklist + SPARQL on `ahu1.ttl` via `rdflib` |

Optional stretch: JSON point export (Day 73).

## Why This Matters

Portfolio closes the track: **wire protocols + dual-stack RDF** for FDD and agents.

## Mini Examples

- Confirm each graded path under `capstone/`.
- Rehearse three Wireshark filters before the final capture.

## Micro Exercises

1. Zip repo subset; include `--help` screenshots.
2. Screen demo: Wireshark filter → CLI read → TTL query (`oxrdf` export + `rdflib` SPARQL).
3. Optional: post one lesson learned to the community.

## Key Takeaway

**Turn-key edge path:** Python BACnet basics → Rust on the wire → **rdflib + oxrdf** semantics for FDD and agents.

## Wireshark Lab

```bash
./capture_pcap.sh day75-final "udp port 47808 or tcp port 443 or tcp port 1502"
```

Document in `pcaps/README.md`:

```
udp.port == 47808
tcp.port == 443 && ip.addr == 192.168.204.11
tcp.port == 1502
```

Congratulations—you finished the **Rust network programming + dual-stack RDF** track.

---

## Python companion — Checklist + SPARQL on `ahu1.ttl`

*Same day as the Rust lesson above. Prefer a venv; `pip install rdflib`. Keep scripts in `~/py-lab`.*

```python
from pathlib import Path
from rdflib import Graph

root = Path("lessons/capstone")  # adjust cwd
for rel in ["discover-and-poll", "niagara-read", "model/ahu1.ttl",
            "graph-export", "pcaps/README.md", "COURSE_REVIEW.md"]:
    p = root / rel
    print(("OK" if p.exists() else "MISSING"), rel)

g = Graph()
g.parse(root / "model" / "ahu1.ttl", format="turtle")
for row in g.query("""
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX ex: <http://example.org/>
SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }
"""):
    print(row.p)
# Rust side: same TTL via oxrdf in graph-export/
```

| Rust (`oxrdf` in `graph-export`) | Python (`rdflib`) |
|--------|--------|
| Capstone CLIs + TTL load/export | `pathlib` checklist + same SELECT |
| Multi-protocol semantic snapshot | Parallel—not a full rewrite |

**Takeaway:** Ship Rust artifacts; Python checklists paths and runs SPARQL on the same `ahu1.ttl`.
