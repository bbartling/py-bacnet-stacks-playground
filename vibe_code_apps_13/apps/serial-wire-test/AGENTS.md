# Phase 1 Agent Rules

Read the root `AGENTS.md` and `docs/PHASE_1_USB_RS485_WIRE_TEST.md` first.

## Allowed

- raw serial/tty configuration;
- private test envelopes and CRC-32;
- deterministic payload generation;
- incremental parsing, reports, timing and fault classification;
- PTY/in-memory integration tests and opt-in real-hardware tests.

## Forbidden

- any BACnet crate or BACnet frame constants;
- MS/TP preamble/frame/token/state-machine code;
- B/IP, UDP, NPDU, APDU, BVLC, routing or web code;
- automatic OS mutation or assumptions about tty enumeration.

## Definition of done

The parser/report/config behavior is covered by normal tests, and a retained real C+C report proves 10,000 alternating exchanges at 38,400 with zero peer errors. Do not call a PTY test a hardware pass.

