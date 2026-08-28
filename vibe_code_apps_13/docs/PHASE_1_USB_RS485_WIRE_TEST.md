# Phase 1 - USB/RS-485 Wire-Test Gate

## Objective

Prove two Waveshare C adapters, two Ubuntu USB paths, A/B/reference wiring, auto-direction, serial configuration and repeatable bidirectional data before introducing BACnet/MS/TP.

Phase 1 is also the source of reusable unit tests for incremental serial parsing, bounded reports, timeout calculation, adapter identity and failure classification.

## Wiring

```text
Ubuntu USB #1 -> Waveshare C adapter A        Waveshare C adapter B <- Ubuntu USB #2

                         A+  =================  A+
                         B-  =================  B-
                  field GND  =================  field GND

                    endpoint                  endpoint
                    120 ohm                   120 ohm
```

Do not connect USB 5 V/VCC terminals. Power off before changing wiring. Confirm individual and combined A/B resistance. Verify network bias separately; the product page's 120-ohm statement describes termination, not a BACnet bias set.

## Ubuntu preflight

```bash
sudo apt-get update
sudo apt-get install --yes build-essential pkg-config libudev-dev usbutils lsof

rustc --version
cargo --version
lsusb
ls -l /dev/serial/by-id/
find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -ls
```

Use unplug/replug observation to map physical A and B to unique by-id entries. Never encode discovery order into configuration.

Serial access:

```bash
sudo usermod -aG dialout "$USER"
```

Log out/in, then verify with `id`. Diagnose owners with `lsof`/`fuser`; do not kill them automatically.

For the FTDI C adapters, inspect the actual tty names first, then:

```bash
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB1/latency_timer
```

Benchmark 1 ms. A permanent udev rule is a later, adapter-specific step.

## Application contract

Create `apps/serial-wire-test` with:

- one async reader per tty;
- one central coordinator that alternates A->B then B->A;
- a private envelope with preamble, version, direction, sequence, length, payload and CRC-32;
- incremental parsing across arbitrary read boundaries;
- bounded resynchronization after noise;
- explicit local-echo classification;
- deterministic boundary/pattern sequence and seeded pseudorandom payloads;
- dynamic deadline based on 10 serial bits/octet plus USB/scheduler margin;
- atomic JSON report;
- bounded SIGINT/SIGTERM and unplug cleanup.

The full implementation prompt is copied into `docs/research/CURSOR_PROMPT_PHASE1_RS485_WIRE_TEST.md` by the installer.

## Test taxonomy

### Unit tests

- envelope encode/decode at every payload boundary;
- split at every byte boundary and one-byte chunks;
- several frames in one buffer;
- leading/inter-frame noise and resync;
- invalid preamble/version/direction/length/CRC;
- oversized declared length rejected before allocation;
- stale/duplicate sequence classification;
- deadlines at all six allowed baud rates;
- atomic report serialization;
- same resolved tty rejected for A and B.

### Integration tests

Use an in-memory duplex or PTY pair. These verify software behavior, not RS-485 hardware.

### Hardware tests

1. 100 alternating rounds at 38,400.
2. 10,000 rounds at 38,400.
3. Repeat at other claimed rates.
4. Unplug B during a bounded run; require clear nonzero failure and partial report.
5. Replug using the same by-id path.
6. Repeat under CPU/log load.
7. After C+C passes, run B+B and B+C as separately labeled comparisons.

## CLI

```text
serial-wire-test \
  --port-a /dev/serial/by-id/... \
  --port-b /dev/serial/by-id/... \
  --baud 38400 \
  --rounds 10000 \
  --max-payload 256 \
  --seed 1337 \
  --report reports/phase1-wire-test.json
```

`--baud` accepts only the six project values and defaults to 38,400.

## Exit checklist

- [ ] C+C wiring, termination and bias arrangement recorded.
- [ ] Adapter model/USB ID/serial/driver/by-id path recorded.
- [ ] FTDI latency setting recorded.
- [ ] Unit and integration tests pass in CI without hardware.
- [ ] Hardware suite is opt-in/ignored by default.
- [ ] 10,000-round C+C report has zero missing, corrupt and duplicate peer frames.
- [ ] Local echo, if present, is harmless and counted separately.
- [ ] Unplug test is bounded and produces a failed report.
- [ ] Phase 1 result is reviewed before adding Phase 2 code.

