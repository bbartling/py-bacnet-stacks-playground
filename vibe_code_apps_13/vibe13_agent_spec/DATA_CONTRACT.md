# Phase 1 data contracts

## Final report — `captures/wire-test-*.json`

Schema: `phase1_wire_v1` (`WireReport` in `crates/lab-common/src/wire/report.rs`)

Key fields for agents and Streamlit:

| Field | Meaning |
|-------|---------|
| `status` | `passed` \| `failed` \| `interrupted` |
| `rounds_completed` / `rounds_requested` | Progress |
| `envelopes_ok_a_to_b`, `envelopes_ok_b_to_a` | Good peer frames per direction |
| `missing`, `corrupt`, `duplicate`, `stale`, `parser_rejected` | Error taxonomy |
| `latency_ms_a_to_b`, `latency_ms_b_to_a` | `{ min_ms, mean_ms, max_ms, samples }` |
| `port_a`, `port_b`, `port_*_resolved` | by-id paths and resolved tty |
| `baud` | 9600–115200 per project policy |

Commit passing hardware reports as evidence; gitignore allows `captures/wire-test-*.json` (not `*-live.json` transient files required in repo).

## Live progress — `captures/<report-stem>-live.json`

Schema: `phase1_wire_progress_v1` (`WireProgress`)

Written every 10 rounds during a run + on completion. Streamlit **Live trunk** polls this file.

| Field | Meaning |
|-------|---------|
| `status` | `running` \| `passed` \| `failed` \| `interrupted` |
| `recent_latency_ms` | Last ~120 RTT samples for sparkline |
| `report_path` | Final report destination |

## Run state — `captures/.wire_test_run.json` (gitignored)

Written by Streamlit when starting a test: `pid`, `cmd`, `report`, `live`, `log`, `baud`, `rounds`.

## Private wire envelope (not BACnet)

Not stored verbatim in reports; on-wire format in Phase 1 only:

```text
Preamble 0x55 0xAA | version | direction | sequence | length | payload | CRC-32
```

See `docs/PHASE_1_USB_RS485_WIRE_TEST.md` and `crates/lab-common/src/wire/envelope.rs`.
