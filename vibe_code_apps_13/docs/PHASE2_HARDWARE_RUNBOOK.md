# Phase 2 — Hardware runbook (NOT EXECUTED)

**Status:** Prepared only. **Phase 2 hardware was not run because the adapters are not installed/wired.**

Do not mark any command below as executed until real captures exist under `captures/`.

## Topology

```text
mstp-probe, MAC 0                 mstp-mini-device, MAC 1
Waveshare C adapter A             Waveshare C adapter B
          A+ ============================== A+
          B- ============================== B-
         REF ============================== REF
```

- Two Waveshare **C** adapters (FT232RNL, hardware auto direction, isolated)
- Device on adapter **B**, probe on adapter **A**
- **No USB 5 V field connection** between adapters
- Exactly **two** endpoint **120 Ω** terminations (no intermediate termination)
- Independent bias verification (do not assume onboard 120 Ω is bias)
- Powered-off A/B resistance expectation ≈ **60 Ω** (two 120 Ω in parallel)
- Prefer stable `/dev/serial/by-id/...` paths
- Operator in `dialout` (do not change groups/udev from the agent)

Placeholders:

- `/dev/serial/by-id/<PROBE_ADAPTER>`
- `/dev/serial/by-id/<DEVICE_ADAPTER>`

Initial baud: **38400** (8N1, no flow control). Shared Max_Master=10, Max_Info_Frames=1.

## Build

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
cargo build --release --locked -p mstp-mini-device -p mstp-probe
```

## Start mini-device (adapter B)

```bash
./target/release/mstp-mini-device \
  --serial /dev/serial/by-id/<DEVICE_ADAPTER> \
  --baud 38400 \
  --mac 1 \
  --max-master 10 \
  --max-info-frames 1 \
  --device-instance 123001 \
  --vendor-id 999
```

## Probe smoke (adapter A)

```bash
./target/release/mstp-probe \
  --profile smoke \
  --baud 38400 \
  --repeated-reads 10 \
  --report captures/mstp-hardware-smoke.json \
  hardware \
  --probe-serial /dev/serial/by-id/<PROBE_ADAPTER> \
  --device-serial /dev/serial/by-id/<DEVICE_ADAPTER>
```

`--device-serial` is **report metadata only** — the probe never opens the device tty.

## Probe gate (≥500 reads)

```bash
./target/release/mstp-probe \
  --profile gate \
  --baud 38400 \
  --repeated-reads 500 \
  --report captures/mstp-hardware-gate.json \
  hardware \
  --probe-serial /dev/serial/by-id/<PROBE_ADAPTER> \
  --device-serial /dev/serial/by-id/<DEVICE_ADAPTER>
```

## Matrix to run on the bench

1. Startup order: device-first / probe-first
2. Sole-master then returning-master admission
3. Duplicate-MAC negative (expect clear failure)
4. Baud-mismatch negative (never false PASS)
5. Unplug / fail-fast
6. 500-read gate
7. One-hour soak
8. Later: per-baud matrix (9600…115200)

## Report expectations

Hardware reports must eventually include Git commit, rusty-bacnet SHA, kernel/arch, by-id paths, USB IDs, driver, actual baud, Max_Master, Max_Info_Frames, termination/bias notes, start/end, exit reason, and `hardware_evidence=true`.

Loopback must never set `hardware_evidence=true`.
