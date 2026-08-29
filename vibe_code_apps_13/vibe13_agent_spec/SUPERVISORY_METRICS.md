# Supervisory metrics — Phase 1 analogs vs real MS/TP

Reference framing for Metasys NAE/SNC, Tridium Niagara JACE, Siemens PXC operators. Phase 1 Streamlit maps **physical-layer** counters; Phase 2+ maps **BACnet MS/TP** counters from `rusty-bacnet`.

## Phase 1 metrics → supervisory analogs (today)

| Metasys/Niagara metric | Phase 1 (now) | Real MS/TP (Phase 2+) |
|------------------------|---------------|------------------------|
| Good frames | Peer envelopes OK (`envelopes_ok_*`) | MS/TP frames + app PDUs |
| CRC errors | `corrupt` + `parser_rejected` | MS/TP CRC-32 |
| Lost tokens | `missing` + `stale` | Token drops / rotation |
| RTT | Envelope round-trip ms (`recent_latency_ms`) | RP/RPM response time |
| Bus load | Estimated from baud × bytes | MS/TP utilization |
| Token TRT | ⚪ N/A until Phase 2 | Full token ring |

## Healthy targets (field MS/TP — for roadmap tab)

| Metric category | Healthy target | Symptom of trouble | Primary root cause |
|-----------------|----------------|--------------------|--------------------|
| Token rotation time | < 300 ms | > 1000 ms (sluggish) | Too many devices, low baud |
| Lost tokens | ≈ 0 | Constantly incrementing | Duplicate MACs, loose wires, low voltage |
| CRC / checksum errors | < 1% of frames | Rapidly climbing | Missing EOL, polarity, EMI |
| Bus load / utilization | 20–50% | > 80% (congested) | Unoptimized Max_Master, heavy polling |

Phase 1 **estimated bus load** and **RTT** on a two-node bench are useful for wiring confidence, not for field trunk sizing.

## Streamlit health states

The **Live trunk** tab computes 🟢🟡🔴 from live JSON:

- **Lost tokens analog:** `missing + stale == 0` → green
- **CRC analog:** `corrupt + parser_rejected == 0` → green
- **RTT:** mean < 300 ms → green; < 500 ms → yellow
- **Bus load estimate:** 20–50% → green; < 80% → yellow

Token TRT row is always ⚪ in Phase 1.
