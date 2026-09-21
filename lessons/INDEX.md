# Rust Network Programming Lab — Days 1–112

**A hands-on network programming course, with BACnet and Modbus as recurring real-world protocols.** Build small tools, understand their bytes on the wire, break them deliberately, and finish able to study and contribute to `diy-bacnet-router`.

**Revision: 2026-09-21. All 112 lesson plans are written. Rust is the primary language; Python companions are optional.** This index and the linked day files define the active course. Old day lessons were replaced directly, with no archive. Live networking and hardware steps remain learner-run labs; [VALIDATION.md](VALIDATION.md) records what was checked during authoring.

Start with the [lab guide](LAB_GUIDE.md), [wire contracts](WIRE_FORMATS.md), [public fixtures](fixtures/README.md), [topology recipes](TOPOLOGIES.md), and [primary references](SOURCES.md). The [review portfolio](capstone/README.md) links the milestones.

## Start here if you are at Day 19

Your completed Python work still counts. Keep your own Day 19 implementation and continue with [Day 20 — Your Day 19 project, now in Rust](day20.md). Days 20–28 give you a practical Rust bridge before sockets and binary parsing become demanding. Do not restart completed work.

New learners follow the rewritten Rust-first Days 1–19, including [the Day 19 review](day19.md). If you already wrote that project in Rust, Day 20 becomes a behavior-preserving refactor and optional independent comparison. Review briefs state behavior, failure cases and evidence, leaving the implementation to you.

## What you will build

| Milestone | Finish | Demonstration |
| --- | --- | --- |
| Rust command-line toolkit | 28 | Parse files and arguments; explain ownership; handle malformed input without a panic. |
| Network detective notebook | 35 | Explain IPv4/IPv6 delivery, routes, neighbors, DNS, and actual capture evidence. |
| Packet inspector | 42 | Decode a documented packet subset and reject malformed/truncated input. |
| UDP field messenger | 49 | Discover lab peers and correlate requests despite loss, duplicates, and timeouts. |
| TCP record service | 56 | Preserve message boundaries across arbitrary reads and writes. |
| **TCP traffic switch** | 63 | Route connections to configured backends; handle slow peers, half-close, and shutdown. |
| Modbus bench toolkit | 70 | Interoperate with an independent peer; explain MBAP, PDU, and RTU framing. |
| BACnet wire explorer | 77 | Decode and correlate discovery and property transactions. |
| BACnet transaction lab | 84 | Explain segmentation and prove bounded transaction behavior with fixtures. |
| BACnet/IP routing bench | 91 | Demonstrate NPDU routing and distinguish it from IP routing and BBMD behavior. |
| **Pi pocket router / WAP** | 98 | Join clients, assign leases, resolve names, route traffic, and recover after reboot. |
| Serial / MS/TP lab | 105 | Explain frame boundaries, CRC, token timing, and measured hardware limits. |
| **DIY BACnet Router study and contribution** | 112 | Trace a real routed request and deliver one bounded, evidence-backed improvement. |

**112 study days instead of 75:** 16 seven-session blocks. “Week” is a teaching block, not a deadline. A normal session is roughly 45–90 minutes: one concept, one small implementation, one experiment. Reviews may take 2–4 hours across a weekend; hardware and capstone sessions may span several evenings. The baseline comes first; extensions are optional. Days 19, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98, 105, and 112 are review milestones, with lighter review projects at 7 and 14. There are 16 review projects in total.

## How to learn without giving away the answers

Ordinary lessons include a goal, prerequisites, a concept, a small distinct example, a coding challenge, an experiment, acceptance checks, an optional Python companion and a stretch. The primary implementations are Rust. Review days give the brief, acceptance criteria and deliverables without a solution or ordered implementation recipe.

Use your own learning repository or `lessons/student-work/`. Public fixtures and [wire contracts](WIRE_FORMATS.md) define expected behavior so independent peers can interoperate. No full course solutions or private answer folder are shipped. Existing code under `capstone/` is explicitly labeled optional reference material and may contain spoilers.

For network reviews, retain source, tests, a bounded capture or labeled fixture, topology and a failure report. For early programming reviews, files and test transcripts are enough. See [the review rubric](LAB_GUIDE.md#review-rubric).

## Language and tool progression

- **Rust owns the implementations:** begin with `std`, explicit types, slices, `Result`, and small tests. Learn blocking sockets before async. From Day 57, use modern `async`/`await`, Tokio, bounded channels, cancellation, and deadlines.
- **Python is an optional lab partner:** `socket`, `struct`, `ipaddress`, and small fixture scripts first; independent Modbus/BACnet libraries later. A Rust server talking to a Python client is more useful than writing two identical servers. The optional companion is normally a 10–20 minute exercise; Rust remains the required implementation. A second Rust process or existing independent tool can serve as the peer.
- **Parse to understand, reuse to integrate:** implement selected codecs in the learning workspace; compare with independent tools. The appliance continues to use pinned upstream rusty-bacnet codecs/transports, not student replacements.
- **Introduce dependencies when needed:** `clap` for CLI UX, `serde` for config/results, `bytes` for buffers, Tokio for concurrency, `tracing` for diagnostics, and established HTTP/TLS crates for management services. Check current primary docs when authoring each lesson; commit `Cargo.lock` and record toolchain/crate versions. Do not copy old book manifests or float the appliance's upstream pin.
- **Tests grow with the risk:** ordinary examples stay small. Parsers need truncation/length tests; streams need split/coalesced input tests; transactions need timer/duplicate tests; routing needs topology and failure evidence. Formatting, Clippy, and relevant tests become routine project checks.

## Layers you will actually touch

OSI is an explanatory map. Internet and BACnet layering do not have a perfect one-to-one correspondence with its seven boxes.

| Layer / boundary | Study and build | Main days |
| --- | --- | --- |
| Physical | Ethernet/Wi-Fi links, UART vs RS-485, termination, turnaround and timing | 93–98, 99–105 |
| Data link | Ethernet/MAC, ARP, VLANs, bridges; MS/TP frames, CRC and tokens | 29–35, 36–42, 90, 99–105 |
| Internet network | IPv4/IPv6 addressing, prefixes, routes, ICMP, NDP, MTU and fragmentation | 29–42, 92–98 |
| Transport | UDP datagrams; TCP streams, sequence/ACK, windows, retransmission, teardown | 43–63 |
| Session / presentation concepts | State machines, deadlines, encodings, TLS, connection lifetime | 36–42, 57–63, 78–84, 109 |
| Application protocols | DNS, DHCP, HTTP, Modbus, BACnet services | 34, 46, 64–91, 94–98, 109 |
| BACnet-specific layering | BVLL/BVLC, NPDU/network messages, APDU/services; multiple data links | 71–91, 99–112 |

Keep these distinctions explicit throughout:

- **Ethernet frame ≠ IP packet ≠ TCP segment / UDP datagram ≠ application message.** A socket receive does not necessarily correspond to a captured packet.
- **IP fragmentation ≠ TCP segmentation ≠ BACnet APDU segmentation.** Each has different boundaries, state, and recovery. BACnet routers forward NPDUs; application segmentation is endpoint transaction behavior.
- **IP subnet ≠ BACnet network number; Ethernet MAC ≠ MS/TP station MAC; IP address ≠ BACnet device instance.** Labs label all of them separately.
- **Linux IP router ≠ TCP proxy ≠ BACnet router ≠ BBMD.** The TCP project terminates two TCP connections. The Pi IP router forwards packets. A BACnet router forwards between BACnet networks. A BBMD distributes BACnet/IP broadcasts across IP subnets.

## Week 1 — Rust programming foundations (Days 1–7)

These lessons use Rust, with optional Python comparisons. Completed work from the earlier course retains its credit.

| Day | Lesson / skill |
| --- | --- |
| [1](day01.md) | [Setup](./day01.md) — Rust/Cargo, editor, run a program; Python optional. |
| [2](day02.md) | [Variables and arithmetic](./day02.md) — numeric values and mutation. |
| [3](day03.md) | [Strings](./day03.md) — distinguish human-readable text from eventual wire bytes. |
| [4](day04.md) | [Numbers and booleans](./day04.md) — ranges, comparisons, validation. |
| [5](day05.md) | [Input and output](./day05.md) — read input and explain failures. |
| [6](day06.md) | [Lists](./day06.md) — collect records; Rust `Vec` companion. |
| [7](day07.md) | [List operations](./day07.md) — consolidation: a small record-reporting tool. |

## Week 2 — Control flow and collections (Days 8–14)

| Day | Lesson / skill |
| --- | --- |
| [8](day08.md) | [For loops](./day08.md) — iterate without hiding the mechanics. |
| [9](day09.md) | [Conditionals and while loops](./day09.md) — decisions and termination. |
| [10](day10.md) | [String operations](./day10.md) — split and validate input. |
| [11](day11.md) | [Dictionaries](./day11.md) — keyed lookup and Rust `HashMap`. |
| [12](day12.md) | [Dictionary loops](./day12.md) — count and summarize records. |
| [13](day13.md) | [Tuples and sets](./day13.md) — group values and recognize duplicates. |
| [14](day14.md) | [Sentinels and loop control](./day14.md) — consolidation: stop cleanly on an explicit condition. |

## Week 3 — Functions, files and the Rust bridge (Days 15–21)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [15](day15.md) | [Functions](./day15.md) — reusable operations. | Small callable units. |
| [16](day16.md) | [Modules](./day16.md) — separate concerns. | Multi-file program. |
| [17](day17.md) | [File I/O](./day17.md) — persistent inputs and outputs. | Read/write example. |
| [18](day18.md) | [Errors](./day18.md) — expected failure as part of the interface. | Bad input does not crash the workflow. |
| **[19](day19.md)** | **[Week 3 Review Project](./day19.md)** — complete the file-to-report challenge or retain credit for your original solution. | Your own solution, missing-file and malformed-data cases. |
| [20](day20.md) | **Port your own Day 19 project to Rust.** Cargo, `fn`, `let`, `match`, `Option`, `Result`, and `?`; identify remaining unfamiliar syntax. | Same valid-input behavior as Python; explicit empty/invalid input behavior. |
| [21](day21.md) | Ownership, moves, borrowing, and `&str` vs `String`, using the port. | Explain one compiler rejection and fix it without cloning every value. |

## Week 4 — Rust tools for network programmers (Days 22–28)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [22](day22.md) | `struct`, `enum`, and `impl`: model an endpoint and a parse outcome. | Invalid states have deliberate handling. |
| [23](day23.md) | Arrays, `Vec<u8>`, slices, UTF-8 vs arbitrary bytes, hexadecimal. | Inspect binary input without assuming text. |
| [24](day24.md) | Ownership across modules; borrowed packet views and introductory lifetimes. | Explain who owns a buffer and how long a view is valid. |
| [25](day25.md) | Traits, generics, `Read`/`Write`, and test doubles. | Run one operation against memory and a file. |
| [26](day26.md) | CLI arguments, config, error context, exit status; introduce `clap`. | Useful help and a malformed-config failure. |
| [27](day27.md) | Unit/integration tests and known-answer fixtures; independent comparison (Python optional). | At least one fixture not generated by the same code being tested. |
| **[28](day28.md)** | **Review: Rust field-tool starter kit.** A CLI that validates endpoint records and emits a report. | Clean build, useful errors, tests, and an ownership explanation. |

## Week 5 — IPv4, IPv6, and packet delivery (Days 29–35)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [29](day29.md) | Encapsulation and OSI/TCP-IP; interfaces, MACs, sockets, ports. Start tcpdump/Wireshark now. | Annotate one packet from application bytes down to link header. |
| [30](day30.md) | IPv4, CIDR, masks, private/link-local/loopback ranges, subnet membership; note /31 and /32 exceptions. | Rust prefix checker with known-answer cases; optional `ipaddress` comparison. |
| [31](day31.md) | Route selection, longest prefix, default gateway, next-hop MAC and ARP. | Predict and capture same-subnet vs routed traffic. |
| [32](day32.md) | IPv6 notation, prefixes, link-local scope IDs, global/ULA addresses, multicast; no broadcast. | Parse and classify IPv6 endpoints, including interface scope. |
| [33](day33.md) | NDP, router advertisements, SLAAC, DHCPv6 distinction, ICMPv6 and dual-stack binds. | Compare neighbor discovery with ARP; explain RA-provided default routes. |
| [34](day34.md) | DNS, A/AAAA, resolver vs wire query, caching, TTL; basic ICMP diagnosis. | Separate name-resolution failure from connect failure. |
| **[35](day35.md)** | **Review: network detective.** Diagnose supplied addressing, route, and resolver faults. | Topology, Rust address tool, captures, and evidence for each diagnosis. |

## Week 6 — Bytes, packet parsing, and capture literacy (Days 36–42)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [36](day36.md) | Byte order, bit masks, checked arithmetic, length fields; implement a tiny bounded binary codec. | Known bytes, round-trip test, truncation at every field boundary. |
| [37](day37.md) | Ethernet headers, EtherType, VLAN tags; capture link types and snap length. | Distinguish Ethernet from Linux cooked/loopback captures before decoding. |
| [38](day38.md) | IPv4 header length/options, total length, TTL, protocol and header checksum. | Decode valid fixtures and reject impossible lengths. |
| [39](day39.md) | IPv6 base header, Next Header, bounded extension-header walking. | Recognize supported headers; report unsupported chains explicitly. |
| [40](day40.md) | UDP/TCP headers, pseudo-header checksums, captured bytes vs offload artifacts. | Compare decoder fields with Wireshark; explain a misleading checksum report. |
| [41](day41.md) | MTU, PMTUD, IPv4 fragmentation and IPv6 source fragmentation; capture vs display filters. | Controlled small-MTU experiment; fragmented input is identified, never misparsed as a full transport header. |
| **[42](day42.md)** | **Review: offline packet inspector.** Use a maintained capture-container reader; implement the selected header decoders yourself. | Supported link types documented, malformed corpus handled, Wireshark field agreement. Full IP reassembly is optional. |

## Week 7 — UDP and discovery (Days 43–49)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [43](day43.md) | Blocking `UdpSocket`, bind addresses, datagram boundaries, receive buffers and timeouts. | Two-process echo interoperability and oversized-message policy. |
| [44](day44.md) | Request IDs, deadlines, retries, duplicate replies and idempotency. | Delayed or duplicated responses do not satisfy the wrong request. |
| [45](day45.md) | Unicast, broadcast, multicast membership and interface selection. | Observe IPv4 broadcast and IPv6 multicast as different mechanisms. |
| [46](day46.md) | Minimal DNS query codec; bounds, names, response correlation and compression-pointer limits. | A/AAAA fixtures; pointer loops/truncation rejected; truncation/TCP fallback recognized. |
| [47](day47.md) | Tiny discovery protocol, versioning and stable identity. | Multiple peers discovered with deduplication and bounded collection time. |
| [48](day48.md) | Fault harness: drop, delay, reorder, duplicate; bounded pacing and retry backoff. | Repeatable seeded test and packet-rate evidence. |
| **[49](day49.md)** | **Review: UDP field messenger.** Discover peers and request a small status payload. | Cross-language peer, loss scenario, bounded memory/time, capture narrative. |

## Week 8 — TCP and application framing (Days 50–56)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [50](day50.md) | `TcpListener`/`TcpStream`, connect/accept, handshake and connection states. | Observe SYN/SYN-ACK/ACK and refusal. |
| [51](day51.md) | Partial reads/writes; TCP is a byte stream, not messages. | Same message decoded from many different input chunkings. |
| [52](day52.md) | Length-prefixed vs delimited messages, maximum sizes, incremental decoder state. | Split and coalesced messages handled; excessive lengths rejected. |
| [53](day53.md) | FIN, half-close, EOF, RST, idle deadlines and stalled peers. | Clean end-of-stream differs from incomplete-message failure. |
| [54](day54.md) | Sequence/ACK, retransmission, receive windows, flow vs congestion control, Nagle. | Explain a controlled slow-reader capture; do not infer congestion from one retransmission. |
| [55](day55.md) | Bounded thread-per-connection service; shared state, locks and connection limits. | Concurrent clients cannot grow resources without limit. |
| **[56](day56.md)** | **Review: TCP record service.** Store/retrieve small opaque records over your framed protocol. | Independent peer, split/coalesced fixtures, slow client, disconnect and size-limit tests. |

## Week 9 — Async Rust and the TCP traffic switch (Days 57–63)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [57](day57.md) | Futures, tasks, `async`/`await`, runtime ownership; port the service to Tokio. | Same protocol contract with concurrent clients. |
| [58](day58.md) | `Send`, `Arc`, locks across await, bounded channels and backpressure. | Slow consumer reaches a deliberate queue limit. |
| [59](day59.md) | `select!`, cancellation safety, timeouts, task joining and graceful shutdown. | Shutdown leaves no forgotten accept/forward tasks. |
| [60](day60.md) | TCP proxy: two connections, bidirectional byte forwarding and half-close propagation. | A client can finish sending and still receive the backend's response. |
| [61](day61.md) | Configured listener-to-backend routing, health checks and connection admission. | New connections handle backend failure; in-flight streams are not silently replayed. |
| [62](day62.md) | Tracing, byte/connection metrics, load experiments and deterministic fault injection. | Explain a slow backend without logging every payload byte. |
| **[63](day63.md)** | **Review: TCP traffic switch.** A small configurable L4 proxy you can run on a Pi. | Two backends, concurrent clients, half-close, outage, shutdown, resource limits and PCAPs. |

Optional fun extension: a delay/drop laboratory for a game-like scoreboard protocol, or a connection-level load balancer. A generic proxy does not invent message boundaries or safely retry arbitrary application writes.

## Week 10 — Modbus as a practical protocol codec (Days 64–70)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [64](day64.md) | Modbus application PDU vs TCP ADU; MBAP fields, transaction ID and unit ID. | Decode captured requests and responses field by field. |
| [65](day65.md) | Implement a narrow read-only TCP client (selected register-read function). | Bounded register count, response validation, exception response handling. |
| [66](day66.md) | Stream reassembly, MBAP lengths, transaction matching and unexpected replies. | Split headers, combined replies, wrong IDs and disconnects tested. |
| [67](day67.md) | Coils/discrete inputs vs registers; address notation, byte/word order and vendor scaling. | Raw register evidence separated from interpretation. |
| [68](day68.md) | RTU ADU, CRC and silent intervals; offline serial frame fixtures. | Explain why TCP has no RTU CRC; physical RTU timing validation deferred to Week 15. |
| [69](day69.md) | Interop against an independent Python or existing Modbus peer; polling budgets. | Normal, exception and timeout captures; no automatic write retries. |
| **[70](day70.md)** | **Review: Modbus bench toolkit.** Inspect frames and poll a simulated register device. | Robust read-only CLI; independent fixtures; TCP/RTU distinction; faulty-server report. |

Optional later extension: a TCP-to-RTU gateway after Week 15. Label it an application gateway with unit-ID mapping and serial arbitration, not a transparent TCP router.

## Week 11 — BACnet wire formats and rusty-bacnet (Days 71–77)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [71](day71.md) | BACnet layer map; device instance, object identifier, property identifier and network address. | Annotated Ethernet/IP/UDP/BVLL/NPDU/APDU capture. |
| [72](day72.md) | BVLC headers/functions/lengths; Original-Unicast/Broadcast and Forwarded-NPDU fixtures. | Decode selected BVLL forms with explicit bounds and unsupported-function behavior. |
| [73](day73.md) | NPDU control bits, optional source/destination fields, hop count and network messages. | Distinguish network-layer messages from APDU-bearing NPDUs. |
| [74](day74.md) | APDU types, invoke IDs, service choice, BACnet tags and lengths. | Decode a small declared subset; reject malformed tag/length input. |
| [75](day75.md) | Who-Is/I-Am using a pinned rusty-bacnet revision; inspect crate boundaries and public APIs. | Real Rust discovery plus independent bacpypes3 client/fixture comparison. |
| [76](day76.md) | Confirmed ReadProperty transaction; simple/complex ACK, Error, Reject and Abort. | Trace one invoke ID from request to outcome with a timeout case. |
| **[77](day77.md)** | **Review: BACnet wire explorer.** Discover lab devices, perform selected reads, and explain the bytes. | Offline fixtures plus isolated live peer; separate device ID, address and network number. |

Small object/property records are needed to speak BACnet. RDF, Brick, SPARQL, Haystack semantic mapping, and graph export are outside this core course.

## Week 12 — BACnet transactions, segmentation and reliability (Days 78–84)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [78](day78.md) | Confirmed-service state, invoke-ID lifecycle, retries and request budgets. | Late and duplicate responses cannot complete the wrong transaction. |
| [79](day79.md) | ReadPropertyMultiple, maximum APDU size, capability negotiation and bounded batching. | Explain when a smaller request is necessary; preserve partial/error outcomes. |
| [80](day80.md) | APDU segmentation: flags, sequence numbers, windows, SegmentACK and endpoint capabilities. | Trace supplied segmented traffic; compare with TCP segmentation and IP fragments. |
| [81](day81.md) | Bounded reassembly/transaction simulator with a fake clock. | Missing, duplicate, out-of-order, wraparound and timeout cases; supported subset stated. |
| [82](day82.md) | COV subscription/renewal, notifications and reconnect/recovery. | Bounded subscription state; polling fallback; captured or fixture-based renewal failure. |
| [83](day83.md) | WriteProperty, priority and NULL release on a disposable simulator only; uncertainty after timeout. | Read-back/release evidence; explain why replaying a write may be unsafe. |
| **[84](day84.md)** | **Review: BACnet transaction lab.** Robust read-only collector plus segmentation evidence notebook. | Independent peer and fault fixtures; supported and unsupported stack capabilities labeled. |

The segmentation simulator is a learning exercise, not an appliance feature claim. When the selected stack/peer lacks a feature, use supplied captures and offline tests and record the limitation rather than fabricate a successful live lab.

## Week 13 — BACnet routing, BBMD and network boundaries (Days 85–91)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [85](day85.md) | Linux namespaces, veth pairs, bridges and a reproducible two-network test bed. | Address/route map, isolated setup and teardown. |
| [86](day86.md) | BACnet route tables and Who-Is-Router-To-Network / I-Am-Router-To-Network. | Route discovery/update fixtures; stale/unreachable route behavior. |
| [87](day87.md) | NPDU forwarding, source/destination network fields and hop-count handling. | Trace directed traffic across two BACnet networks using existing stack APIs. |
| [88](day88.md) | Local, remote and global broadcasts; loop prevention and forwarding bounds. | Broadcast matrix and hop-exhaustion negative case. |
| [89](day89.md) | BACnet/IP subnet crossing: BBMD, BDT/FDT, foreign registration and expiry. | Separate broadcast distribution from BACnet network routing using captures/fixtures. |
| [90](day90.md) | VLAN vs subnet vs BACnet network; firewall/NAT effects; BACnet/IPv6 and BACnet/SC overview. | Draw what each mechanism changes; treat IPv6/SC as separate protocol support to verify. |
| **[91](day91.md)** | **Review: two-network BACnet routing bench.** Forward between distinct BACnet networks over two B/IP ports. | Independent endpoint read, network-message/broadcast cases, unavailable-route fault, captures on both sides. |

A BBMD lab can use an established external implementation. It does not imply that `diy-bacnet-router` implements BBMD/FDR, BACnet/IPv6, or BACnet/SC.

## Week 14 — Raspberry Pi pocket router, WAP and DHCP (Days 92–98)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [92](day92.md) | Build/deploy the Rust tools to a Pi; Linux interfaces and service lifecycle. | Record OS, architecture, toolchain, interface names and binary revision. |
| [93](day93.md) | Ethernet/USB NICs, Wi-Fi AP capability, bridge vs routed LAN, uplink vs client network. | Actual hardware topology and non-overlapping address plan. |
| [94](day94.md) | DHCPv4 Discover/Offer/Request/Ack, lease lifetime/options and renewal; decode selected fields in Rust. | Lease capture and bounded malformed-option fixtures; established daemon serves leases. |
| [95](day95.md) | DNS forwarding/cache, leases and local names; service binding and port conflicts. | A client resolves names; DNS failure differs from DHCP failure. |
| [96](day96.md) | Linux forwarding, routing, nftables and IPv4 NAT; separate IPv6 RA/SLAAC and firewall policy. | LAN/uplink captures show forwarding/NAT; management exposure is deliberate. |
| [97](day97.md) | WAP bring-up, client isolation, reboot recovery, link loss and bounded Rust health reporting. | Join, renew, reconnect, restart and uplink-loss tests. |
| **[98](day98.md)** | **Review: pocket lab network.** Portable Pi router/WAP plus the Rust TCP traffic switch and diagnostics. | Two clients obtain leases, resolve names, reach an allowed upstream service, and recover after reboot; rollback documented. |

**“DHCP for USB devices” means USB network interfaces.** USB Ethernet adapters or supported USB Ethernet gadget links can carry IP and DHCP. USB RS-485 adapters and arbitrary USB peripherals do not get DHCP leases. Gadget mode depends on the Pi model, controller and port; verify before planning it. The baseline uses an uplink interface plus a separate LAN interface/AP. Verify AP support and regulatory settings on the actual adapter; do not assume one radio can provide both AP and Wi-Fi uplink.

Use the chosen OS's supported networking stack: NetworkManager shared/hotspot mode **or** deliberately managed hostapd/dnsmasq services. One component owns each interface/DHCP service. The Rust work is a DHCP decoder, diagnostic client and health service; writing a complete DHCP server, Wi-Fi driver, NAT engine or TCP stack is not required. On IPv6, default-router discovery comes from RA; DHCPv6 is not an IPv4 DHCP gateway-option replacement. Keep DHCP on the isolated lab LAN with a separate management/recovery path.

## Week 15 — Serial, RS-485 and BACnet MS/TP (Days 99–105)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [99](day99.md) | UART vs RS-485, 8N1, baud, wiring, bias, termination and direction control. | Wiring diagram and passive-only bench check before transmission. |
| [100](day100.md) | Stable serial paths, exclusive ownership, reads in chunks, stop/reopen and USB latency. | Disconnect and restart behavior; one process owns each tty. |
| [101](day101.md) | Modbus RTU physical timing vs host timestamps; compare to TCP-to-serial expectations. | Independent read-only RTU peer or recorded trace; measured limits stated. |
| [102](day102.md) | MS/TP preamble, frame type, source/destination, header/data CRC and resynchronization. | Offline Rust decoder with corrupt/truncated frame corpus. |
| [103](day103.md) | Token, Poll For Master, Max_Master, Max_Info_Frames and reply timing. | Trace a recorded token cycle and a small state-machine simulation. |
| [104](day104.md) | Passive capture first, then a controlled multi-station lab using the pinned stack. | Token/CRC/timeout evidence; baud and exact topology recorded. |
| **[105](day105.md)** | **Review: serial field notebook.** Explain a good trunk and diagnose supplied faults. | Decoder tests, serial evidence, timing limits and orderly stop/reopen; no invented hardware pass. |

Ethernet tcpdump cannot see RS-485 electrical traffic. Use a suitable passive serial capture setup or recorded serial frames, and export to Wireshark only with the correct supported encapsulation. A pseudo-terminal tests byte streams, not RS-485 electrical behavior or token timing. The current DIY router bench documents **38400 as its default/live-trunk hold**; coursework uses a separate isolated bench and does not retune a shared trunk.

## Week 16 — Study and improve DIY BACnet Router (Days 106–112)

| Day | Skill / challenge | Evidence |
| --- | --- | --- |
| [106](day106.md) | Read repo contract, architecture, test ledger and upstream lock; draw crate responsibilities. | Separate intended behavior, source evidence, exact-image evidence and open gates. |
| [107](day107.md) | Trace config validation → transport construction → router start → local delivery → stop. | Annotated call graph with actual source locations at the checked-out revision. |
| [108](day108.md) | Reproduce dual-B/IP routing tests, then investigate one failing or deliberately faulted case. | Baseline and fault evidence with both interfaces captured. |
| [109](day109.md) | HTTP/REST, JSON framing, TLS trust/identity, WebSocket lifecycle and slow management consumers. | A small Rust management client; observe TLS via a controlled TLS endpoint; demonstrate data/management separation. |
| [110](day110.md) | Select one bounded improvement: parser regression upstream, shutdown test, clearer diagnostic or reproducible lab. | Problem statement, failing test or repeatable evidence, and correct repository ownership. |
| [111](day111.md) | Implement and verify; study Buildroot/QEMU/Pi deployment and repeat an available gate. | Relevant repo checks; source vs VM/image vs physical hardware clearly separated. |
| **[112](day112.md)** | **Final review: router field demonstration and contribution.** Explain a routed ReadProperty end to end and defend one improvement. | Source/PR-ready patch, tests, topology, captures/logs, known limitations and a runbook another learner can follow. |

The final goal is to understand and make a credible contribution to an unfinished router, not finish its entire product backlog in seven sessions. Hardware completion has a separate badge: if equipment is unavailable, finish the software track with dual-B/IP and explicitly sourced pinned-upstream MS/TP fixtures, and leave physical B/IP↔MS/TP and exact-image validation visibly pending.

## Lab ladder and evidence rules

| Level | Environment | What it proves |
| --- | --- | --- |
| A | One Linux computer: fixtures, loopback, Rust or optional Python peer | Codecs, sockets, transactions and failure handling. |
| B | Linux namespaces/veth or separate VMs | Routes, broadcast boundaries, firewall/NAT and multi-interface behavior. |
| C | Pi plus laptop; second Pi/client for richer topology | Deployment, real NIC/Wi-Fi behavior, DHCP/DNS and restart recovery. |
| D | Isolated RS-485 bench with suitable adapters and independent stations | Electrical/link/timing behavior for the exact recorded topology. |
| E | Built appliance image on QEMU or actual Pi | Image/service behavior; hardware claims require the actual hardware. |

No hardware purchase is required to start. Before Week 14, inventory existing Pis, NICs, AP capability, ports and adapters; then choose a topology. Most early labs run on Linux loopback. Namespace/network-administration operations occur in a disposable lab environment, with cleanup and a recovery path. Writes and active serial experiments use disposable peers, never an occupied building control loop.

For each capture lab, record: program and dependency revisions, OS/kernel, interface/link type, topology, addresses/ports, capture command/filter, Wireshark display filter, bounded duration/size, frame references, expected result, observed result, and limitations. Use explicit names such as `tcp-half-close.pcapng`. Keep private payloads/credentials out of shared fixtures. Explain capture offload and timestamp limitations before claiming checksum or timing faults.

## Reading Packt with current Rust

Use [Packt's Network Programming with Rust repository](https://github.com/PacktPublishing/Network-Programming-with-Rust/tree/master) as a **project idea bank and historical comparison**. Its sockets → parsing → services → concurrency → security progression fits this course. Read the intent, write your implementation against current primary documentation, then compare designs. Do not spend a week reviving obsolete dependency APIs before learning the underlying concept.

The chapter/example paths below were inspected during this revision; this is a topic crosswalk, not a promise that those examples build on the course toolchain.

| Book examples | New course | Modernization task |
| --- | --- | --- |
| Chapter02: `hello-rust`, `factorial` | 20–28 | Cargo, ownership and errors through useful command-line tools. |
| Chapter03: `ipnetwork-example`, `tcp-echo-random`, `pnet-example`, `mio-example`, `trust-dns-example` | 29–63 | Prefixes, packet inspection, blocking sockets first, then readiness vs async; check current DNS library APIs. |
| Chapter04: `nom-ipv6`, `nom-http`, `serde-*` | 36–42, 51–52, 109 | Explicit binary bounds first; parser libraries and serialization after the wire contract is understood. |
| Chapter05: FTP/TFTP, gRPC and mail examples | Optional after 63 | Choose one protocol extension; keep Modbus/BACnet as the main applied work. |
| Chapter06: Hyper, Reqwest, Rocket examples | 109, optional HTTP extension | A bounded HTTP exercise plus maintained client/server libraries for actual management APIs. |
| Chapter07: futures, streams and Collatz examples | 57–63 | Modern `async`/`await`, Tokio tasks, cancellation and bounded queues. |
| Chapter08: Rustls/OpenSSL/TLS examples | 109 | Certificate identity/trust and current Rustls APIs; use established cryptography. |
| Chapter09: parser, parallelism and async appendix | Optional extensions | Separate CPU parallelism from I/O concurrency; measure before optimizing. |

Primary references to use when rewriting lessons:

- [The Rust Book](https://doc.rust-lang.org/book/) and [standard networking APIs](https://doc.rust-lang.org/std/net/) — language and blocking sockets.
- [Tokio tutorial](https://tokio.rs/tokio/tutorial) — modern async, channels, framing and shutdown; [Rustls](https://docs.rs/rustls/latest/rustls/) — TLS implementation and examples.
- [Wireshark User's Guide](https://www.wireshark.org/docs/wsug_html_chunked/) — capture workflow, filters, stream analysis and reassembly.
- [IPv4 RFC 791](https://www.rfc-editor.org/rfc/rfc791), [IPv6 RFC 8200](https://www.rfc-editor.org/rfc/rfc8200), [TCP RFC 9293](https://www.rfc-editor.org/rfc/rfc9293), [NDP RFC 4861](https://www.rfc-editor.org/rfc/rfc4861), and [DHCP RFC 2131](https://www.rfc-editor.org/rfc/rfc2131) — field/procedure references, read selected sections alongside captures.
- [Modbus Organization specifications](https://www.modbus.org/modbus-specifications) — application protocol and TCP/serial implementation guides.
- [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) — inspect the selected revision and tests; protocol authority remains the applicable ASHRAE 135 standard and addenda, not a README feature list.
- [Raspberry Pi configuration documentation](https://www.raspberrypi.com/documentation/computers/configuration.html) — verify instructions for the actual OS release and hardware rather than copy an old hotspot tutorial.

## The destination repository: a reading map

Local checkout: `/home/ben/Desktop/diy-bacnet-router`. These are **study targets**, not files modified by this syllabus.

| Read | Question to answer |
| --- | --- |
| `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md` | What is the appliance promising, and what has actually been demonstrated? |
| `config/upstream-lock.toml`, `docs/UPSTREAM_LOCK.md`, `Cargo.toml` | Which upstream APIs/revision are we studying, and what is the update gate? |
| `crates/router-core/src/config.rs`, `runtime.rs`, `metrics.rs` | Which contracts and bounds are independent of protocol/HTTP implementation? |
| `crates/rusty-bacnet-adapter/src/validate.rs`, `ports.rs` | How do valid settings become actual B/IP and MS/TP transports? |
| `crates/rusty-bacnet-adapter/src/route_session.rs`, `local_delivery.rs` | Who owns forwarding, local traffic and shutdown? |
| `crates/rusty-bacnet-adapter/src/dual_bip.rs`, `bip_qualify.rs`, `mstp_passive.rs`, `mstp_qualify.rs` | How is behavior proven before enabling a live path? |
| `crates/routerd/src/main.rs`, `web.rs`, `system.rs` | How does the process expose management without blocking the data plane? |

At inspection, the local README distinguishes source routing evidence from still-open exact-image/hardware gates. Re-read the ledger at Day 106; this course does not freeze those statuses. Keep bacpypes3 outside the appliance as an independent oracle on a separate host/IP. Do not transplant a mini-device object database into the router or substitute student codecs for upstream transport internals.

## Using the finished lesson plans

All 112 linked day files are now the active Rust-first course. The old generators were removed so they cannot overwrite the new sequence. The README and filter sheet use the new numbering. No archive is retained, per the course owner's preference.

The plans are authored; they are not a claim that all physical labs have been executed. [VALIDATION.md](VALIDATION.md) separates document/example/fixture checks from live stack, Pi, serial and exact-image evidence. Repeat relevant checks when changing dependencies or adapting a lab to a different OS.

Optional unrelated tracks remain available: [Bandit](bandit/README.md), [grid-search lessons](grid_search/INDEX.md), and existing Haystack/semantic code in the repository. They are not dependencies of this course.

Optional follow-on blocks beyond Day 112: TUN/TAP IPv4 forwarding, a userspace UDP tunnel, DNS proxy/cache, HTTP reverse proxy, QUIC comparison, Modbus TCP↔RTU gateway, BACnet/SC with a supported stack, or a reproducible Buildroot image. Each should have prerequisites, a bounded subset, an independent peer, fault cases and a review project.
