# serial-wire-test

Phase 1 dual USB RS-485 wire tester. Opens two adapters, alternates private framed envelopes (not BACnet), writes a JSON report.

See [`docs/PHASE1_CHEATSHEET.md`](../../docs/PHASE1_CHEATSHEET.md) and [`docs/PHASE_1_USB_RS485_WIRE_TEST.md`](../../docs/PHASE_1_USB_RS485_WIRE_TEST.md).

```bash
# identify adapters first
../../scripts/show-adapters.sh

cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_A \
  --port-b /dev/serial/by-id/REPLACE_B \
  --baud 38400 --rounds 100 \
  --report captures/wire-test-smoke.json
```

Unit/parser tests run without hardware (`cargo test -p lab-common`). Hardware is opt-in via real `--port-*` paths.
