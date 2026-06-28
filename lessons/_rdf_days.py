# Days 56-75 RDF in Rust — imported by generate_rust_days.py
LESSONS_RDF = {
56: """## Day 56 – URIs, Prefixes & QNames in Rust

### Goal

Represent **IRIs** and **prefix maps** with `HashMap<String, String>` and expand `brick:AHU` by hand.

### Concept

```rust
use std::collections::HashMap;

fn expand(map: &HashMap<&str, &str>, qname: &str) -> Option<String> {
    let (prefix, local) = qname.split_once(':')?;
    map.get(prefix).map(|base| format!("{base}{local}"))
}

fn main() {
    let mut pm: HashMap<&str, &str> = HashMap::new();
    pm.insert("brick", "https://brickschema.org/schema/Brick#");
    pm.insert("ex", "http://example.com/bldg#");
    println!("{}", expand(&pm, "brick:AHU").unwrap());
}
```

### Why This Matters

RDF tools merge models from BACnet exporters, Haystack tags, and Brick—**shared identity strings** prevent collisions.

### Mini examples

- Expand `ex:OA-T` and `brick:Outside_Air_Temperature_Sensor`.
- Store full IRI as `String` in triples.

### Micro exercises

1. Function `is_brick(qname: &str) -> bool`.
2. Why HTTPS IRIs for Brick namespace?
3. Convert one Haystack tag path to a fake `ex:` IRI convention.

### Key takeaway

**Prefix maps are just HashMaps**—SPARQL `PREFIX` blocks do the same thing in query text.
""",
57: """## Day 57 – Triples & Literals as Rust Types

### Goal

Model **RDF triples** and **typed literals** with enums—not strings everywhere.

### Concept

```rust
#[derive(Debug, Clone)]
enum RdfObject {
    Iri(String),
    Literal { lex: String, datatype: Option<String> },
}

#[derive(Debug, Clone)]
struct Triple {
    s: String,
    p: String,
    o: RdfObject,
}

fn triple(s: &str, p: &str, lit: &str, dt: &str) -> Triple {
    Triple {
        s: s.into(),
        p: p.into(),
        o: RdfObject::Literal {
            lex: lit.into(),
            datatype: Some(dt.into()),
        },
    }
}
```

### Why This Matters

Distinguishing **node vs literal** prevents bugs like treating `"72.5"` as a sensor identity.

### Mini examples

- Triple with object IRI `ex:AHU1`.
- Literal `"72.5"^^xsd:double` as struct fields.

### Micro exercises

1. `Vec<Triple>` for one AHU + SAT point.
2. Display impl printing Turtle-like one-liners.
3. Match on `RdfObject` in a function `is_literal`.

### Key takeaway

**Enums express RDF grammar** better than Python tuples alone.
""",
58: """## Day 58 – Reading Turtle (By Hand, Then Parse Lite)

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
""",
59: """## Day 59 – Adjacency List Graph in Rust

### Goal

Implement a **directed multigraph** as `HashMap<String, Vec<(String, RdfObject)>>` for queries by subject.

### Concept

```rust
use std::collections::HashMap;

type AdjGraph = HashMap<String, Vec<(String, RdfObject)>>;

fn add(g: &mut AdjGraph, t: &Triple) {
    g.entry(t.s.clone()).or_default().push((t.p.clone(), t.o.clone()));
}

fn objects_of<'a>(g: &'a AdjGraph, subj: &str, pred: &str) -> Vec<&'a RdfObject> {
    g.get(subj)
        .into_iter()
        .flat_map(|v| v.iter())
        .filter(|(p, _)| p == pred)
        .map(|(_, o)| o)
        .collect()
}
```

### Why This Matters

This is your **mini rdflib Graph**—enough for Brick traversals without SPARQL engine complexity.

### Mini examples

- Query all `brick:hasPoint` for `ex:AHU1`.
- Count triples: sum edge list lengths.

### Micro exercises

1. Function `types_of(g, subj)` using `rdf:type` IRI constant.
2. Merge two graphs (insert all edges).
3. Dedupe edges with a `HashSet` of serialized keys.

### Key takeaway

**Graph = map of subject → outgoing edges**—classic CS 101 structure, building semantics.
""",
60: """## Day 60 – rdf:type & Brick Class Taxonomy

### Goal

Navigate **`rdf:type`** and **`rdfs:subClassOf`** chains for Brick equipment classes in your adjacency graph.

### Concept

Constants:

```rust
const RDF_TYPE: &str = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const RDFS_SUBCLASS: &str = "http://www.w3.org/2000/01/rdf-schema#subClassOf";
```

Query pattern: find all nodes where type is `brick:AHU` or subclass thereof (walk `subClassOf` edges upward in a tiny static taxonomy map).

### Why This Matters

FDD rules reference **Brick class names** as logical columns—types tell you which points belong to which equip templates.

### Mini examples

- Add `brick:AHU rdfs:subClassOf brick:Equipment` manually.
- List all instances of `brick:Sensor` in toy graph.

### Micro exercises

1. Hard-code 5-class hierarchy in TTL; load into graph.
2. Function `is_instance_of(g, node, class_iri) -> bool` (BFS over subclass).
3. Link to open-fdd rule inputs that mention Brick classes.

### Key takeaway

**Taxonomy = typed nodes + subclass edges**—RDF's core OOP-like view of buildings.
""",
61: """## Day 61 – Haystack Tags vs Brick Graphs

### Goal

Compare **Haystack tag dictionaries** (Zinc/CSV) with **Brick RDF graphs**—when to use which on projects.

### Concept

Haystack row (conceptual):

```
id,dis,equipRef,curVal,unit
@ahu1.oa-t,"OA Temp",@ahu1,55.3,°F
```

Brick graph:

```
ex:ahu1-oat rdf:type brick:Outside_Air_Temperature_Sensor .
ex:ahu1 brick:hasPoint ex:ahu1-oat .
```

Rust bridge:

```rust
fn haystack_row_to_triples(id: &str, equip: &str) -> Vec<Triple> {
    // emit rdf:type and brick:hasPoint triples — simplified lab
    vec![]
}
```

### Why This Matters

Niagara speaks Haystack; analytics ontologies speak Brick—**edge Rust services translate**.

### Mini examples

- Convert one golden Zinc row to 2–3 triples.
- Tags not in Brick—store as `ex:tag "key" "value"` literal triples optional.

### Micro exercises

1. Table: 3 things Haystack does well vs 3 things Brick does well.
2. Implement stub `haystack_row_to_triples` returning at least one triple.
3. Where does rusty-haystack stop and RDF begin?

### Key takeaway

**Tags for ops/runtime; graphs for mergeable semantics**—you need both in modern BAS stacks.
""",
62: """## Day 62 – Hand-Author Brick Model for One AHU

### Goal

Write **`ahu1.ttl`** by hand for one AHU, SAT, OAT, and **`brick:hasPoint` / `brick:feeds`** (if applicable).

### Concept

Minimum entities:

- `ex:AHU1` a `brick:AHU`
- Points: SAT, OAT as appropriate sensor classes
- Optional: `ex:VAV1 brick:isFedBy ex:AHU1` if in scope

Load into Day 59 graph; verify counts.

### Why This Matters

Commissioning deliverables increasingly include **semantic models** alongside BACnet point lists.

### Mini examples

- Validate Turtle with online parser or `oxrdf` load.
- Pretty-print via your Display impl.

### Micro exercises

1. At least 8 triples in TTL file.
2. Query all points of AHU1 from Rust graph code.
3. Screenshot Turtle + Rust query output for portfolio.

### Key takeaway

**Small accurate models beat huge auto-generated junk**—hand authoring builds intuition.
""",
63: """## Day 63 – Pattern Matching Queries (SPARQL Mindset in Rust)

### Goal

Implement **graph pattern matching** like a tiny SPARQL `SELECT ?p WHERE { ex:AHU1 brick:hasPoint ?p }` in Rust loops.

### Concept

```rust
fn select_points(g: &AdjGraph, ahu: &str) -> Vec<String> {
    let pred = "https://brickschema.org/schema/Brick#hasPoint";
    g.get(ahu)
        .into_iter()
        .flat_map(|edges| edges.iter())
        .filter_map(|(p, o)| {
            if p == pred {
                if let RdfObject::Iri(iri) = o { Some(iri.clone()) } else { None }
            } else {
                None
            }
        })
        .collect()
}
```

### Why This Matters

Before using a SPARQL engine, understand **pattern matching as nested loops** over triples.

### Mini examples

- Two-pattern query: points that are `brick:Temperature_Sensor`.
- Return count only (SPARQL `COUNT` mindset).

### Micro exercises

1. Function `ask_exists(g, pattern)` returning bool.
2. Optional filter: literal curVal > 50 (if you added sensor values).
3. Compare to SQL JOIN intuition in one paragraph.

### Key takeaway

**SPARQL is declarative graph pattern matching**—Rust loops are the engine underneath student implementations.
""",
64: """## Day 64 – Multi-Protocol Bench PCAP Challenge

### Goal

One capture, **three display filters**—BACnet UDP, Haystack HTTPS, Modbus TCP—document what each shows.

### Concept

```bash
PCAP_SECONDS=45 ./capture_pcap.sh day64-multi \\
  "udp port 47808 or tcp port 443 or tcp port 1502"
```

Bench reference:

- BACnet: `192.168.204.200:47808`
- Haystack: `192.168.204.11:443`
- Modbus: `192.168.204.14:1502` (if enabled)

### Why This Matters

Open-FDD runs **multiple drivers**—one edge host, many transports (Day 35 map in production).

### Mini examples

- IO graph per filter.
- Table: protocol, transport, port, tool that generated traffic.

### Micro exercises

1. Three screenshots with three filters applied.
2. Which protocol is easiest to decode without TLS keys?
3. Write one sentence per protocol for your README portfolio.

### Key takeaway

**Wireshark is multi-protocol**—display filters switch lenses on the same file.

### Wireshark Lab

Filters (apply one at a time):

1. `udp.port == 47808`
2. `tcp.port == 443 && ip.addr == 192.168.204.11`
3. `tcp.port == 1502`
""",
65: """## Day 65 – open-fdd Drivers & Semantic Layer

### Goal

Relate **Rust drivers** (BACnet, Haystack, Modbus) in open-fdd to the graphs you build—conceptual architecture day.

### Concept

Layers:

1. **Transport** — UDP/TCP (this course Weeks 5–6)
2. **Driver** — rusty-bacnet / HTTP client / modbus crate
3. **Normalization** — point IDs, units, timestamps
4. **Semantics** — Brick/RDF tags for rules (FDD expressions)

Read: `open-fdd` workspace driver configs and commission CSVs if available locally.

### Why This Matters

You aren't learning Rust in a vacuum—you're learning **edge BAS architecture**.

### Mini examples

- Diagram: BACnet PV → internal point id → Brick class column for rule.
- List env vars that disable BACnet server on commission host (lab lesson learned).

### Micro exercises

1. Trace one point from Wireshark BACnet frame to FDD rule input name (conceptual).
2. Where would `ahu1.ttl` live in a deployment story?
3. MCP/agent prompts that reference drivers—skim open-fdd agent prompt if present.

### Key takeaway

**Network programming enables drivers; RDF enables reasoning across drivers.**
""",
66: """## Day 66 – Serialize Graph to Turtle from Rust

### Goal

Write **`graph.serialize_turtle()`**—emit prefixes and triples from your adjacency structure.

### Concept

```rust
impl AdjGraph {
    fn to_turtle(&self, prefix_map: &HashMap<&str, &str>) -> String {
        let mut out = String::new();
        for (pfx, iri) in prefix_map {
            out.push_str(&format!("@prefix {pfx}: <{iri}> .\n"));
        }
        // emit "subj pred obj ." lines — simplify IRIs with prefixes when possible
        out
    }
}
```

Round-trip: TTL → graph → TTL should preserve triple count.

### Why This Matters

Exporting models for **Brick validation tools** and partners requires serialization—not only in-memory graphs.

### Mini examples

- Round-trip `ahu1.ttl` through parse (if using oxrdf) and your serializer.
- Git-diff two exports—stable sort lines for clean diffs.

### Micro exercises

1. Serialize Day 62 model from code-built graph.
2. Handle literal datatypes in output `^^xsd:double`.
3. Unit test: parse count == serialize count.

### Key takeaway

**RDF interoperability is file exchange**—Turtle generation completes the Rust RDF mini-stack.
""",
67: """## Day 67 – ASHRAE 223P & Brick Alignment (Concept)

### Goal

High-level **223P** vs **Brick** vs **Haystack**—where RDF fits industry standards without reading the full standard.

### Concept

- **Brick**: RDF ontology for buildings (classes, relationships)
- **Haystack**: tag taxonomy + REST ops (often Zinc, not always RDF export)
- **223P**: ASHRAE semantic model effort—RDF-oriented; aligns with Brick ecosystem in many discussions

Rust role: store **223P-aligned IRIs** as `String`s in same graph as Brick—future-proof naming.

### Why This Matters

Course ends at **RDF in Rust**, not Python rdflib—223P is the "why this is standardized" capstone context.

### Mini examples

- One paragraph each: Brick, Haystack, 223P audience.
- Pick one AHU relationship expressible in Brick and name 223P-equivalent intent (qualitative).

### Micro exercises

1. No code required—reading notes + link to public Brick/223P primer docs.
2. Optional: add comment in TTL `# aligns with 223P intent: system boundary`.
3. How would rusty-haystack + RDF export compose on an edge node?

### Key takeaway

**Standards are shared graphs**—Rust services produce/consume them at the edge.
""",
68: """## Day 68 – Integrate BACnet Read → RDF Triples

### Goal

Pipeline sketch: **ReadProperty** in Rust → update literal triple for current value linked to Brick point node.

### Concept

```rust
fn update_curval(g: &mut AdjGraph, point_iri: &str, value: f64) {
    let pred = "http://www.w3.org/1999/02/22-rdf-syntax-ns#value"; // example; use project predicate
    let lit = RdfObject::Literal {
        lex: format!("{value}"),
        datatype: Some("http://www.w3.org/2001/XMLSchema#double".into()),
    };
    g.entry(point_iri.into()).or_default().push((pred.into(), lit));
}
```

Run read loop every N seconds; graph holds **latest** snapshot (historian is separate).

### Why This Matters

This is the **unity node** of the whole course: Python BACnet → Rust network → Rust RDF.

### Mini examples

- Link BACnet object map from Day 53 to Brick IRI keys.
- Log triple count each poll.

### Micro exercises

1. One point end-to-end: BACnet read → println triple.
2. PCAP + log timestamp correlation.
3. Error path: BACnet fail doesn't corrupt graph.

### Key takeaway

**Live OT data can feed semantic models**—do it safely read-only on lab points.
""",
69: """## Day 69 – FILTER & OPTIONAL Patterns in Rust

### Goal

Implement SPARQL-like **`FILTER`** (numeric compare) and **`OPTIONAL`** (maybe-missing edges) on your graph API.

### Concept

```rust
fn optional_point_label(g: &AdjGraph, pt: &str) -> Option<String> {
    let label_pred = "http://www.w3.org/2000/01/rdf-schema#label";
    objects_of(g, pt, label_pred).into_iter().next().and_then(|o| match o {
        RdfObject::Literal { lex, .. } => Some(lex.clone()),
        _ => None,
    })
}
```

FILTER: keep sensors where parsed literal > threshold.

### Why This Matters

Real models miss labels, units, or optional points—queries must not explode on absence.

### Micro exercises

1. Query all temperature sensors with optional `rdfs:label`.
2. Filter SAT > 55.0 if literal present.
3. Compare to SQL LEFT JOIN in one sentence.

### Key takeaway

**OPTIONAL = left join mindset**—essential for commissioning-grade incomplete graphs.
""",
70: """## Day 70 – UNION & ASK Queries

### Goal

Implement **`UNION`** (two patterns, merge results) and **`ASK`** (exists?) for commissioning checks.

### Concept

ASK example: "Does AHU1 have any Supply Air Temperature sensor?"

```rust
fn ask_has_sat(g: &AdjGraph, ahu: &str) -> bool {
    select_points(g, ahu).iter().any(|p| {
        types_of(g, p).iter().any(|t| t.contains("Supply_Air_Temperature"))
    })
}
```

UNION: merge results from two predicates or two equipment branches.

### Why This Matters

Commissioning scripts ask yes/no questions before trend analysis—ASK is the RDF form.

### Micro exercises

1. ASK three rules on your `ahu1.ttl` model.
2. UNION query for two different sensor class patterns.
3. Print PASS/FAIL report markdown from Rust `main`.

### Key takeaway

**Existence checks are first-class**—not everything is a SELECT table.
""",
71: """## Day 71 – DISTINCT, ORDER BY, LIMIT in Rust

### Goal

Query hygiene: dedupe results, sort, cap row count—like SPARQL post-processing in application code.

### Concept

```rust
fn select_distinct_sorted(mut ids: Vec<String>) -> Vec<String> {
    ids.sort();
    ids.dedup();
    ids.truncate(10);
    ids
}
```

Apply after pattern match functions from Days 63–70.

### Why This Matters

UI and agent tools need **top-k** points, not 10k triple dumps.

### Mini examples

- LIMIT 5 points for dashboard card.
- ORDER BY IRI for stable CLI output.

### Micro exercises

1. Wrap Day 63 query with distinct + limit flags.
2. Benchmark naive vs sorted dedupe on 1k fake triples (optional).
3. Document why DISTINCT matters after UNION.

### Key takeaway

**Practical query engines add SQL-like polish**—even hand-rolled Rust matchers.
""",
72: """## Day 72 – Haystack RDF Export Path (Concept + Stub)

### Goal

Explore whether your Haystack source exposes **RDF** or only Zinc—and stub an export pipeline `Zinc rows → triples`.

### Concept

If only Zinc:

1. `/read` → parse grid
2. Map columns `id`, tags → triples (Day 61)
3. Merge with Brick template graph

Optional crates: `oxrdf`, `rio_turtle` for standards-compliant IO.

### Why This Matters

"Haystack RDF" in industry often means **tag projection into RDF**, not Niagara native RDF files.

### Mini examples

- List triple count from Haystack-derived vs hand Brick TTL.
- Note tags without Brick mapping → `ex:haystackTag` annotation.

### Micro exercises

1. Implement `zinc_row_to_triples` for 3 columns.
2. Merge Haystack-derived graph with `ahu1.ttl`.
3. One-page doc: what your site would need for RDF export.

### Key takeaway

**RDF at the edge is often synthesized** from Haystack reads + Brick ontology rules.
""",
73: """## Day 73 – Agent-Ready Point Metadata (Rust Structs → JSON)

### Goal

Serialize query results as **JSON** for MCP/agents—network + semantics course meets AI edge workflows.

### Concept

```rust
#[derive(serde::Serialize)]
struct PointRow {
    iri: String,
    brick_class: String,
    cur_val: Option<f64>,
    bacnet_ref: Option<String>,
}
```

Use `serde_json` to emit NDJSON for agent consumption.

### Why This Matters

open-fdd agent prompts reference **driver health + point context**—JSON bridges RDF graphs to LLM tools.

### Mini examples

- One JSON line per temperature sensor after graph query.
- Include `bacnet_ref` from Day 53 map.

### Micro exercises

1. `cargo add serde serde_json`.
2. Emit file `points.ndjson` from combined pipeline stub.
3. Validate JSON with `jq .` per line.

### Key takeaway

**Agents don't speak SPARQL first—they speak JSON**—Rust serves both graph and tool APIs.
""",
74: """## Day 74 – Course Review: Python → Rust → Wire → Graph

### Goal

Write a **one-page architecture doc** tying Days 1–27 Python to Days 28–73 Rust outcomes.

### Concept

Sections to include:

1. What you kept from Python BACnet intuition
2. UDP/TCP labs and Wireshark filters you use weekly
3. rusty-bacnet + rusty-haystack roles
4. RDF graph API you built vs old Python rdflib track
5. Bench diagram with IPs

### Why This Matters

Solid learning sticks when you **integrate**, not when you finish day 75 and forget day 36.

### Mini examples

- Timeline photo: pcap + CLI output + TTL file.
- List 5 Wireshark filters from [wireshark_filters.md](./lab-scripts/wireshark_filters.md) you actually used.

### Micro exercises

1. Submit `COURSE_REVIEW.md` in your lab folder.
2. Re-run Day 46 + Day 54 capstones—both still work?
3. Teach a peer one UDP vs TCP difference using your pcap.

### Key takeaway

**You now speak field protocols and semantic graphs in Rust**—the Python weeks were foundation, not wasted.
""",
75: """## Day 75 – Final Capstone: Multi-Protocol Semantic Snapshot

### Goal

Deliver **`capstone/`** with:

1. **`discover-and-poll`** — Rust BACnet CLI (Day 46 quality)
2. **`niagara-read`** — Haystack CLI (Day 54 quality)
3. **`model/ahu1.ttl`** — Brick hand model (Day 62)
4. **`graph/`** — Rust binary loading TTL + BACnet live read → merged Turtle export (Day 68 + 66)
5. **`pcaps/README.md`** — three filters used on one multi-protocol capture (Day 64)
6. **`COURSE_REVIEW.md`** (Day 74)

### Concept

Grading rubric (self-check):

| Artifact | Pass criteria |
|----------|----------------|
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
""",
}
