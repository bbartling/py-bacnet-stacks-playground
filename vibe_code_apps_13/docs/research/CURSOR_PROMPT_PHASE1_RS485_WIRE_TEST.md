# Cursor Prompt — Phase 1: Same-PC Dual USB-RS-485 Wire Test

Copy everything between `BEGIN CURSOR PROMPT` and `END CURSOR PROMPT` into Cursor Agent mode while opened at the repository root.

---

## BEGIN CURSOR PROMPT

You are implementing **Phase 1 only** of a Linux BACnet MS/TP lab. The goal is to prove two real USB-to-RS-485 adapters and their physical A/B wiring by exchanging raw framed bytes in both directions. Do not implement BACnet, MS/TP, a token state machine, a router, a web dashboard, MCP, or a Linux kernel line discipline in this phase.

The workstation is an Ubuntu x86 tower with multiple USB ports and at least two Waveshare USB-to-RS-485 adapters. Both adapters will be plugged into the same PC and physically connected to each other. One Rust process will open both serial ports, transmit through the real RS-485 transceivers, and verify what the opposite adapter receives.

Use the two **Waveshare USB TO RS485 (C)** adapters for the primary Phase 1 acceptance run. They use FT232RNL and are explicitly optically isolated. The available USB TO RS485 (B) adapters use CH343G and are useful later as a second driver/transceiver comparison, but do not mix models during the first baseline. After C+C passes, run B+B and finally B+C as separately labeled compatibility experiments. The B model may enumerate through Linux CDC-ACM as `ttyACM*`; the C model normally uses FTDI's driver and may enumerate as `ttyUSB*`. Always discover the actual device paths.

First inspect the existing repository and preserve its Markdown research files and any user changes. Do not delete, reset, or overwrite unrelated files. Do not commit unless explicitly asked.

### Desired result

After wiring and Ubuntu setup, this command should run 10,000 alternating A→B and B→A exchanges and write a machine-readable report:

```bash
cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_WITH_ADAPTER_A \
  --port-b /dev/serial/by-id/REPLACE_WITH_ADAPTER_B \
  --baud 38400 \
  --rounds 10000 \
  --max-payload 256 \
  --report captures/wire-test-38400.json
```

Success means zero missing, duplicate, or corrupt peer frames, with bidirectional traffic proven over the two physical adapters. The program must exit nonzero on data corruption, timeout, configuration error, or unexpected loss.

## Physical wiring documentation to create

Create `docs/PHASE1_WIRING_AND_UBUNTU.md` and include this schematic, adapting terminal labels only if the actual adapter documentation uses different names:

```text
                       UBUNTU x86 TOWER
              ┌────────────────────────────────┐
              │                                │
USB port #1 ──┤  Waveshare adapter A           │
              │  /dev/serial/by-id/...A        │
              │          A+  o──────────────────────────────o  A+
              │          B-  o──────────────────────────────o  B-
              │     GND/REF  o──────────────────────────────o  GND/REF
              │                                             Waveshare adapter B
USB port #2 ──┤                                             /dev/serial/by-id/...B
              │                                │
              └────────────────────────────────┘

                 one short, daisy-chained RS-485 segment
                 Adapter A is one physical end
                 Adapter B is the other physical end
```

Also include this terminal table:

```text
Adapter A terminal       Adapter B terminal
------------------       ------------------
A or A+              →   A or A+
B or B-              →   B or B-
GND / signal reference→  GND / signal reference
```

State the following clearly:

1. Unplug both USB adapters before installing or changing the wires.
2. Connect A to A and B to B. Use the printed terminal labels, not wire colors.
3. Connect only the RS-485 signal reference/GND terminals intended by the adapter manual. Do not join USB 5 V terminals, external supply outputs, chassis earth, or protective earth between the adapters.
4. Do **not** connect `5V`, `VCC`, or another power terminal between these USB-powered adapters.
5. Keep the initial cable short. The two adapters are the two physical ends; do not form a star.
6. Terminate only the two ends. If both models already contain a 120-ohm terminator, do not add external terminators.
7. With both adapters unplugged and the bus unpowered, measure resistance across A/B. Approximately 60 ohms indicates two 120-ohm terminations in parallel. Approximately 120 ohms usually means only one termination; approximately 40 ohms usually means three 120-ohm loads. Treat unexpected readings as a wiring/configuration issue before testing.
8. Confirm the exact Waveshare model and whether its termination and bias resistors are fixed, switched, or absent. Do not guess from another Waveshare model.
9. The intended FTDI Waveshare unit controls transmit direction automatically. Use normal serial mode. Do not enable `TIOCSRS485`, RTS direction, GPIO direction, or software toggling in Phase 1.
10. Begin at 38,400 baud, 8 data bits, no parity, one stop bit, no hardware/software flow control.

Add a short warning that a successful short-cable test does not validate long field trunks, grounding, noise, bias, surge protection, or interoperability. It proves the adapters, ports, wire, and raw byte path.

## Ubuntu preparation section

Place the following commands in the runbook with explanations. The scripts/code must never assume that adapter A is always `ttyUSB0`.

### 1. Install native build prerequisites

```bash
sudo apt-get update
sudo apt-get install --yes build-essential pkg-config libudev-dev usbutils lsof
```

Then verify Rust separately:

```bash
rustc --version
cargo --version
```

If Rust is absent, tell the user to install a current toolchain using the official Rust installation instructions and then rerun the version checks. Do not silently install Rust from an unreviewed script.

### 2. Plug in and identify both adapters

```bash
lsusb
ls -l /dev/serial/by-id/
find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -ls
```

For each actual tty, whether `ttyUSB*` or `ttyACM*`, inspect udev properties. These are examples; replace them with the nodes actually discovered:

```bash
udevadm info --query=all --name=/dev/ttyUSB0
udevadm info --query=all --name=/dev/ttyUSB1
readlink -f /sys/class/tty/ttyUSB0/device
readlink -f /sys/class/tty/ttyUSB1/device
```

Tell the user to label the physical devices “A” and “B” and record each `/dev/serial/by-id/...` path. Include a safe identification method: unplug only adapter B, observe which by-id entry disappears, plug it back in, then confirm it reappears. Repeat for A if necessary. No application should be running during that process.

If the devices do not expose unique serial-number paths, document that physical USB port identity can be used for a custom udev alias, but do not invent a rule without inspecting the actual `udevadm` output.

### 3. Grant non-root serial access

```bash
sudo usermod -aG dialout "$USER"
```

Tell the user to log out and back in, then verify:

```bash
id
ls -l /dev/serial/by-id/
```

Normal test execution must not require `sudo`.

### 4. Check whether another service owns the ports

Replace the tty names with the real resolved paths:

```bash
sudo lsof /dev/ttyUSB0
sudo lsof /dev/ttyUSB1
sudo fuser --verbose /dev/ttyUSB0
sudo fuser --verbose /dev/ttyUSB1
```

If ModemManager or another process is probing the adapters, report the evidence. Do not globally disable a service unless the user chooses to do so. Prefer a narrowly scoped `ID_MM_DEVICE_IGNORE` udev rule based on verified device properties if one is needed.

### 5. Inspect FTDI latency

This check applies to the C/FT232RNL pair. A B/CH343G adapter using Linux CDC-ACM will not use the same FTDI sysfs control.

```bash
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB1/latency_timer
```

Explain that these nodes may not exist for every driver/kernel. If present and currently higher than 1, provide the temporary test commands:

```bash
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB1/latency_timer
```

The user must first verify that the tty names correspond to adapters A and B. Do not install a permanent udev rule in this phase; merely document what an eventual narrowly scoped rule would accomplish.

### 6. Watch kernel hotplug/error messages

In a separate terminal:

```bash
sudo dmesg --follow
```

Do not use `stty` as a persistent setup step. The Rust application must configure both ports itself and report the effective requested settings at startup.

## Rust workspace to implement

Use a small Cargo workspace that can be extended in later phases:

```text
Cargo.toml
Cargo.lock
crates/
  lab-common/
    Cargo.toml
    src/lib.rs
  serial-wire-test/
    Cargo.toml
    src/main.rs
captures/
  .gitkeep
docs/
  PHASE1_WIRING_AND_UBUNTU.md
  PHASE1_TEST_RESULTS.md
```

`lab-common` should contain reusable serial settings, wire envelope types/parser, report types, and timing helpers. `serial-wire-test` should contain the CLI and coordinator.

Use the current stable versions compatible with the installed Rust toolchain of:

- `tokio`;
- `tokio-serial`;
- `clap` with derive support;
- `serde` and `serde_json`;
- `crc32fast`;
- `rand`, `rand_chacha`;
- `tracing` and `tracing-subscriber`;
- `anyhow` or a typed error crate.

Commit `Cargo.lock` because this is an executable workspace. Keep dependencies minimal and explain any extra dependency in the handoff.

## CLI requirements

Required arguments/options:

```text
--port-a PATH             required; prefer /dev/serial/by-id
--port-b PATH             required; must differ from port A
--baud RATE               default 38400
--rounds COUNT            default 100
--max-payload BYTES       default 256, hard bounded
--seed U64                default fixed documented seed
--timeout-ms MS           optional override; otherwise calculated safely
--turnaround-guard-ms MS  default small positive guard, e.g. 5
--report PATH             required for acceptance runs
--log LEVEL               default info
```

Validate before opening either port:

- paths are nonempty and not the same resolved device;
- baud is positive and supported by `tokio-serial`/driver;
- rounds is positive and bounded against accidental huge runs;
- max payload is within the private protocol limit;
- timeout and guard are reasonable;
- report parent directory exists or is created safely within the requested location.

Print a startup summary with port paths, their resolved canonical targets when possible, baud, 8N1, flow control off, round count, payload limit, seed, timeout policy, and report path.

Request exclusive serial access where the Unix API supports it. If the port is busy or missing, return a concise actionable error naming that port. If port B fails to open after A opened successfully, close A during cleanup.

## Private wire envelope

This protocol exists only to validate the raw wire. It is not an MS/TP frame:

```text
Offset  Size  Field
0       2     preamble 0x55 0xAA
2       1     version, initially 1
3       1     direction: 0xA1 for A→B, 0xB1 for B→A
4       4     sequence number, big endian
8       2     payload length, big endian
10      N     payload
10+N    4     CRC-32 over bytes 2 through 9+N
```

Implement explicit encode/decode code; do not serialize a Rust struct representation directly. The decoder must:

- accept arbitrary read fragmentation;
- decode multiple envelopes received in one read;
- resynchronize by scanning for the preamble after noise or a malformed frame;
- reject unsupported version or direction;
- reject payload lengths larger than the configured hard maximum before allocating;
- verify CRC-32;
- preserve enough diagnostic information to report why a frame was rejected;
- avoid unbounded buffer growth if random data never contains a valid frame.

## Test coordinator behavior

Use one async reader per port and a central coordinator. Each reader continuously reads incremental bytes, feeds its parser, and emits events tagged `PortA` or `PortB` through a bounded channel.

For each round:

1. choose a payload length from the required boundary set, then from deterministic pseudorandom values up to `max-payload`;
2. choose the required test pattern: all-zero, all-one, `0x55`, `0xAA`, byte ramp, or seeded pseudorandom;
3. create the A→B envelope with the next sequence;
4. write the entire encoded envelope to port A and flush the async writer;
5. wait for the matching frame on port B before the calculated deadline;
6. if the same frame appears on port A, classify it as local echo and count it separately, not as peer success or corruption;
7. after successful reception, wait the configured turnaround guard;
8. create and send the B→A envelope and verify it on A using the same rules;
9. record latency, length, pattern, direction, retries (normally zero), local echo, parse errors, unexpected frames, and serial errors.

Do not write both ports simultaneously in the baseline. This is a half-duplex alternating test.

Calculate the default timeout from the envelope's approximate wire time at 10 serial bits per byte plus generous USB/scheduler margin. It must handle 256-byte frames at 9,600 baud without false timeout. A suitable policy is at least 1 second and at least four times calculated wire duration plus 100 ms. Report the chosen deadline.

The coordinator must not let a local-echo or stale event satisfy a later transaction. Match direction, sequence, length, payload, and CRC. Bound all channels and retained diagnostics.

On SIGINT/SIGTERM, stop creating new rounds, close tasks cleanly, write a partial report marked `interrupted`, and return a distinct nonzero exit status.

## Required payload sequence

Ensure the run includes these lengths when `max-payload` permits:

```text
0, 1, 2, 7, 8, 15, 16, 31, 32, 63, 64,
127, 128, 254, 255, 256
```

Required patterns:

```text
all 0x00
all 0xFF
all 0x55
all 0xAA
incrementing byte ramp
seeded ChaCha pseudorandom bytes
```

Cycle deterministically through boundary lengths/patterns before using random combinations. A failed seed, round, direction, length, and pattern must appear in console output and JSON.

## JSON report

Write atomically through a temporary file followed by rename. Include:

- schema version;
- application version/Git commit if available;
- status: passed, failed, or interrupted;
- UTC start/end timestamps and elapsed duration;
- OS/kernel and architecture when easily available without privilege;
- requested port paths and resolved tty paths;
- baud/8N1/flow-control settings;
- rounds requested/completed;
- envelopes and payload bytes sent/received per direction;
- local-echo counts per source port;
- missing, corrupt, duplicate, stale, unexpected, parser-rejected, and serial-error counts;
- latency min/mean/median/p95/p99/max per direction;
- seed, payload limit, timeout policy, and guard time;
- first bounded set of detailed failure records;
- final pass/fail reason.

Do not claim success if the report cannot be written.

## Unit and non-hardware tests

Add deterministic tests for:

1. encode/decode round trips for every boundary length and pattern;
2. each possible split point in an encoded envelope;
3. one byte at a time input;
4. several envelopes in one input buffer;
5. noise before/between frames and correct resynchronization;
6. bad preamble, version, direction, length, and CRC;
7. oversized declared length without large allocation;
8. truncated frame awaiting additional data without busy-looping;
9. duplicate/stale sequence classification;
10. timeout calculation at 9,600, 38,400, and 76,800 baud;
11. JSON report serialization and atomic replacement helper;
12. CLI rejection of the same resolved port for A and B.

Use in-memory byte chunks for parser tests. Hardware tests must be explicitly ignored/tagged so `cargo test --workspace` succeeds without adapters.

## Commands to document and execute when hardware is available

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo build --release --workspace
```

First visible run:

```bash
RUST_LOG=info cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_WITH_ADAPTER_A \
  --port-b /dev/serial/by-id/REPLACE_WITH_ADAPTER_B \
  --baud 38400 \
  --rounds 100 \
  --max-payload 256 \
  --report captures/wire-test-smoke.json
```

Acceptance run:

```bash
RUST_LOG=info cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_WITH_ADAPTER_A \
  --port-b /dev/serial/by-id/REPLACE_WITH_ADAPTER_B \
  --baud 38400 \
  --rounds 10000 \
  --max-payload 256 \
  --report captures/wire-test-38400.json
```

Then repeat at 9,600 and 76,800 baud only if the adapter specifications support those rates.

## Manual fault check

After the successful 100-round smoke run, start another 100-round run and unplug adapter B. The program must:

- fail within a bounded timeout;
- identify which peer transaction failed;
- avoid a tight retry/spin loop;
- close port A and all tasks;
- write a failed or interrupted partial JSON report;
- exit nonzero.

After replugging, the same `/dev/serial/by-id/...` path should work again without editing the command.

## Phase 1 acceptance gate

Update `docs/PHASE1_TEST_RESULTS.md` with a checklist and a place to paste actual report summaries. Phase 1 passes only when:

- wiring/termination/reference arrangement is documented with adapter models;
- both unique by-id paths are recorded;
- both directions pass through the physical RS-485 transceivers;
- the 10,000-round 38,400-baud run has zero missing, duplicate, or corrupt peer frames;
- local echo, if present, is separately measured and harmless;
- unplugging a peer gives a bounded actionable failure;
- formatting, Clippy, and unit tests pass;
- the JSON report is retained in `captures/` or referenced from the test results.

Do not begin BACnet/MS/TP code if this gate fails.

## Working style and final handoff

Work incrementally. Inspect actual crate APIs and compiler errors rather than guessing. Keep the user informed of material assumptions. Do not modify operating-system state automatically: Ubuntu setup, udev, group, latency, and physical wiring commands belong in the runbook for the user to execute deliberately.

At completion:

1. summarize the implemented files;
2. list every command actually run and its outcome;
3. distinguish unit-test success from hardware-test status;
4. state clearly if real adapters were not available to the agent;
5. give the exact next three commands the user should run on Ubuntu;
6. do not claim Phase 1 passed without a real 10,000-round hardware report.

## END CURSOR PROMPT
