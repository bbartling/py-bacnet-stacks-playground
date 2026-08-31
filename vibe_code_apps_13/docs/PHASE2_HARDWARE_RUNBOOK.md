# Phase 2 — Hardware runbook (BASRT + JCI FEC + Waveshare C)

**Status (2026-08-31):** Prototype closed — historical runbook. Software pin **`af4e886`** (`jscott3201/rusty-bacnet` — #467/#468 merged). Gates 2–4 hardware **PASS** on `af4e886` (2026-08-31 smoke). Gates 5–6, 1h/24h soak **not run**.

## Reference adapter

[Waveshare USB TO RS485 (C)](https://www.waveshare.com/usb-to-rs485-c.htm) — FT232RNL, isolated, **hardware automatic direction**, onboard **120 Ω** termination. See [`../README.md`](../README.md#hardware-baseline) for bench photo and termination rules. **Do not** enable kernel RS-485 ioctl / RTS / GPIO direction on this adapter.

**Upstream:** [#467](https://github.com/jscott3201/rusty-bacnet/pull/467) and [#468](https://github.com/jscott3201/rusty-bacnet/pull/468) **merged**. Limitations: not conformance; no extended frames; Gates 5–6 open.

## Topology (current)

```text
BASRT-B, MAC 0                  JCI FEC, MAC 7               Linux/Waveshare C
physical endpoint              middle device                physical endpoint
termination enabled            termination disabled          fixed ~130 ohms
         |                            |                            |
         +----------------------------+----------------------------+
               + to +, - to -, REF/common to REF/common
```

| Setting | Value |
|---------|--------|
| Baud | 38,400 |
| BASRT MS/TP MAC / net | 0 / 2000 |
| FEC MAC / device instance | 7 / 5007 |
| Rust station MAC | **3** (never 0 with BASRT; never 7) |
| Mini-device instance | 123001 |
| Max_Info_Frames (initial) | 1 |
| rusty-bacnet | `jscott3201/rusty-bacnet` @ `af4e88680c51eb4da64dac47f0540a35bf184732` |

Powered-off trunk A/B should read ≈ **60–65 Ω**. ≈40–45 Ω ⇒ three terminations — fix before TX.

Do **not** add a second Waveshare C as midspan tap (extra fixed termination).

## Serial path

```bash
PORT=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0
TTY="$(readlink -f "$PORT")"
ls -l "$PORT"; fuser -v "$TTY" || true
cat "/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
```

## Build

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
cargo build --release --locked -p mstp-passive-sniff -p mstp-fec-diag -p mstp-mini-device
```

## Gate 2 — Passive (no TX)

```bash
cargo run --release --locked -p mstp-passive-sniff -- \
  --serial "$PORT" --baud 38400 --seconds 60 \
  --report captures/mstp-passive-af4e886-60s.json
```

PASS: report **`ok=true`** (command exit 0), `rx_bytes>0`, `tokens>0`, sources include **0 and 7**, `token_0_from_7>0`, Workbench stays online, **no Rust TX**. Historical `captures/mstp-passive-crc-fixed.json` (`rusty_bacnet_rev` `6a70b85`) is archived — not evidence for `af4e886`.

## Gate 3 — Client-only FEC

**Status:** PASS on pin `af4e886` (2026-08-31 one-shot; historical `e3b9edb` on `19d205d` archived).

`mstp-fec-diag` always does setup reads (I-Am / object-name / AI) then optional loops.

**One-shot (setup + one periodic read — `--loop-count 1`):**

```bash
cargo run --release --locked -p mstp-fec-diag -- \
  --serial "$PORT" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 5007 --expect-mac 7 --ai-instance 1173 \
  --settle-ms 30000 --apdu-timeout-ms 15000 \
  --loop-secs 30 --loop-count 1 \
  --report captures/mstp-fec-ai1173-oneshot.json
```

**Five 30s reads (operator watches Workbench):**

```bash
cargo run --release --locked -p mstp-fec-diag -- \
  --serial "$PORT" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 5007 --expect-mac 7 --ai-instance 1173 \
  --settle-ms 30000 --apdu-timeout-ms 15000 \
  --loop-secs 30 --loop-count 5 \
  --report captures/mstp-fec-ai1173-5x30s.json
```

**Twenty 30s soak (only after five-read coexistence holds):**

```bash
cargo run --release --locked -p mstp-fec-diag -- \
  --serial "$PORT" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 5007 --expect-mac 7 --ai-instance 1173 \
  --settle-ms 30000 --apdu-timeout-ms 15000 \
  --loop-secs 30 --loop-count 20 \
  --report captures/mstp-fec-ai1173-30s.json
```

Read-only vs FEC. Never WriteProperty to the FEC.

## Gate 4 — Mini-device server-only

**Status: PASS (2026-08-31, pin `af4e886`)** — JENEsys discovered `device:123001` / points Polled `{ok}` while FEC stayed online.

Stop any other holder of `$PORT`, then:

```bash
cargo run --release --locked -p mstp-mini-device -- \
  --serial "$PORT" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 123001 --name "Rust MS/TP Mini Device" --vendor-id 999
```

In Workbench: Who-Is / discover on the MS/TP network → **Rust MS/TP Mini Device**.

## Gate 4b — Haystack trunk (supervisory, parallel evidence)

Requires `HAYSTACK_USER` / `HAYSTACK_PASS` (e.g. from `~/open-fdd/.env`):

```bash
./scripts/check_mstp_haystack_trunk.sh check          # before/after functional matrix
./scripts/check_mstp_haystack_trunk.sh perturb-stop-mini   # mini-device stopped; FEC still ok
./scripts/check_mstp_haystack_trunk.sh restore      # after mini-device restarted
```

## Gates 5–6

**OPEN.** Combined endpoint + mirror + long soak — not claimed.

## rusty-bacnet pin

`jscott3201/rusty-bacnet` @ `af4e886…` (dev after #467/#468). Historical: `bbartling` @ `19d205d…`.

