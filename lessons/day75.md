## Day 75 – Final Capstone: Multi-Protocol Semantic Snapshot

### Goal

Deliver **[`capstone/`](./capstone/)** with:

1. **`discover-and-poll/`** — Rust BACnet CLI ([Day 46 starter](./capstone/discover-and-poll/))
2. **`niagara-read`** — Haystack CLI via [nhaystack-niagara-pi-tutorial](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) ([pointer](./capstone/niagara-read/README.md))
3. **`model/ahu1.ttl`** — Brick hand model ([starter included](./capstone/model/ahu1.ttl))
4. **`graph-export/`** — Rust binary loading TTL + BACnet live read → merged Turtle ([starter](./capstone/graph-export/))
5. **`pcaps/README.md`** — three filters used on one multi-protocol capture ([template](./capstone/pcaps/README.md))
6. **`COURSE_REVIEW.md`** ([template](./capstone/COURSE_REVIEW.md))

### Concept

Grading rubric (self-check):

| Artifact | Pass criteria |
|----------|---------------|
| BACnet CLI | Reads device 5007 without panic; logs errors |
| Haystack CLI | Basic auth works; prints Zinc or parsed rows |
| TTL model | ≥8 triples; valid Turtle |
| Graph export | Round-trip triple count ≥ original |
| PCAP doc | Shows BACnet + HTTPS + filter strings |

Optional stretch: JSON point export for agents (Day 73).

### Why This Matters

This replaces the old Day 75 SPARQL-on-rdflib capstone with **Rust-native networking + RDF** aligned to edge BAS reality.

### Micro exercises

1. Zip repo subset; include `--help` screenshots.
2. Record 2-minute screen demo: Wireshark filter → CLI read → TTL query.
3. Post one Discord/forum lesson learned (community optional).

### Key takeaway

**Turn-key edge practitioner path:** Python BACnet basics → Rust protocols on the wire → semantic models for FDD and agents.

### Wireshark Lab

Final capture:

```bash
./capture_pcap.sh day75-final "udp port 47808 or tcp port 443 or tcp port 1502"
```

Document filters in `pcaps/README.md`:

```
udp.port == 47808
tcp.port == 443 && ip.addr == 192.168.204.11
tcp.port == 1502
```

Congratulations—you finished the **Rust Network Programming + RDF** track.
