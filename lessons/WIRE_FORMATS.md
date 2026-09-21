# Public wire contracts for teaching projects

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md)

These small formats are invented for the course. They are **not** BACnet, Modbus, or production standards. Field definitions and externally observable behavior are public so independently written peers can interoperate. They do not prescribe parser structure, algorithms or function names. Real protocol lessons use their primary specifications.

## Teaching envelope

Used by Day 36 and selected packet fixtures. All multibyte integers are big-endian.

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 1 | Version; only 1 supported |
| 1 | 1 | Kind; only 1 or 2 supported |
| 2 | 2 | Payload length, excluding the four-byte header; 0–256 |
| 4 | length | Opaque payload |

Known-answer example: `01 02 00 03 61 62 63` is version 1, kind 2, with payload bytes spelling ASCII `abc`. The entire message is seven bytes. A single-message/datagram decoder rejects trailing bytes, unsupported fields and impossible lengths. A stream-oriented adaptation may retain incomplete input, but must expose final truncation at EOF. Those are different input contracts.

## Field messenger

Used by Days 44–49. This is a **new format**, not an undocumented change to the Day 36 header. One UDP datagram contains exactly one message. Header integers are big-endian.

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 1 | Version 1 |
| 1 | 1 | Kind: 1 Discover request; 2 Status request; 129 Discovery reply; 130 Status reply |
| 2 | 2 | Request ID copied by the reply |
| 4 | 2 | Payload length excluding the six-byte header; maximum 256 |
| 6 | length | Kind-specific payload |

Discover has an empty payload. Status request has a four-byte unsigned peer ID. Both reply kinds carry a four-byte peer ID followed by 0–64 bytes of printable ASCII status text (space through `~`). This makes the reply payload at most 68 bytes. A malformed request may be dropped; the baseline has no wire error reply. A status request for another ID receives no reply. IDs identify claimed peers, not authenticated devices.

Example request: `01 02 12 34 00 04 00 00 00 07` requests status from peer 7 with request ID 0x1234. Its matching status reply must have version 1, kind 130, request ID 0x1234, peer ID 7 and valid lengths/text. Other fields are not accepted merely because the request ID matches.

For unicast transactions, correlate the sender endpoint, request ID and expected reply kind/peer ID. Discovery can collect replies from several endpoints; keep at most 32 unique peer IDs during a two-second collection window. Conflicting identity claims are reported, not silently overwritten. At most three sends occur within a two-second overall transaction deadline; unrelated packets do not extend it. Use monotonic time. Choose and document exact retry spacing. No write operations are defined.

## TCP record service

Used by Days 52–56 and as traffic for the proxy. Each frame has a two-byte big-endian payload length, then that many payload bytes. Payload length is 0–1024. The framing layer accepts an empty frame; the command layer returns invalid-command for it. Excessive frame length is a framing error: close the connection rather than attempting unlimited resynchronization.

Commands are binary, not newline-delimited:

| Opcode | Request payload |
| --- | --- |
| 1 PUT | opcode[1], key_length[1], key[key_length], value[remaining bytes] |
| 2 GET | opcode[1], key_length[1], key[key_length]; no trailing bytes |
| 3 PING | opcode[1]; no trailing bytes |

Keys are 1–32 ASCII letters, digits, hyphens or underscores. Values are opaque 0–256 bytes. Store at most 32 keys. PUT overwrites an existing key; at capacity a new key fails without evicting an old one. The in-memory store persists only for the server process lifetime. No durability or cross-process synchronization is required.

Response payload starts with one status byte:

| Status | Meaning and remaining response bytes |
| --- | --- |
| 0 | Success; GET appends the exact stored value; PUT and PING append nothing |
| 1 | Missing key; no further bytes |
| 2 | Invalid command/key/value shape; no further bytes |
| 3 | Store full; no further bytes |

Responses use the same outer length prefix. Process requests in order on each connection, with one response per validly framed request. The client knows which pending operation a response answers; no request ID is defined here. A valid frame containing an invalid command gets status 2 and may be followed by more frames. An incomplete frame at final EOF is a connection error; do not invent a response by filling missing bytes.

Baseline limits: four concurrent clients, three-second idle timeout, two-second shutdown drain deadline. Publish your overload admission policy. A peer that half-closes after complete requests can still receive responses. Idle timeouts alone need not defend against every slow trickle; extensions may add a total frame deadline. The generic TCP proxy treats these frames as opaque bytes.

## Segmentation simulator

Used by Day 81. This is a receive-window-one **teaching model**, not a complete BACnet segmentation state machine. Do not send its event rows directly on a real BACnet network.

A test starts with peer/context, invoke ID, expected sequence, monotonic start time and deadline. Default initial sequence is 0. A wraparound test may start from a explicitly declared continuation snapshot expecting 254; that is not a valid claim that a real new BACnet transfer starts at 254.

Each event has time, peer/context, invoke ID, sequence 0–255, more-follows flag, and payload bytes. Events are processed in nondecreasing time order. At or after the fixed deadline, the transfer expires. Wrong-context events do not append data or extend the deadline. A matching expected sequence appends its payload exactly once and advances expected sequence modulo 256. A duplicate of the most recently accepted sequence causes a duplicate acknowledgement observation but no second append. Other sequences are rejected/out-of-order observations. The first accepted event cannot be labeled a duplicate merely by subtracting one from the initial expected sequence.

An accepted event with more-follows false completes the transfer. Completed or expired transfers do not reopen on later events. Cap accepted segments at 32 and total payload at 4096 bytes; exceeding either fails explicitly before appending. Output records accepted bytes, outcome and event classifications. Window negotiation, sender behavior, full retransmission rules, negative SegmentACK procedures and multiple simultaneous transfers are outside this subset.
