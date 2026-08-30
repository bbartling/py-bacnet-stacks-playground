# Phase 2 — Hardware runbook (BASRT + JCI FEC + Waveshare C)

**Status (2026-08-30):** Live midspan/end-of-line bench exists. Loopback ≠ hardware PASS.  
**Active rescue prompt:** Phase 2 Rescue (CRC Clause 9 + gates 1–6). Historical Cursor plan `vibe13_ms_tp_usb_fix_*` is obsolete.

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
| BASRT Max_Master | 127 |
| FEC MAC / device instance | 7 / 5007 |
| Rust station MAC | **3** (never 0 with BASRT; never 7) |
| Mini-device instance | 123001 |
| Max_Info_Frames (initial) | 1 |

Powered-off trunk A/B should read ≈ **60–65 Ω**. ≈40–45 Ω ⇒ three terminations — fix before TX.

Do **not** add a second Waveshare C as midspan tap (extra fixed termination).

## Serial path

```bash
PORT=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0
TTY="$(readlink -f "$PORT")"
ls -l "$PORT"; fuser -v "$TTY" || true
cat "/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
# If not 1, human runs: echo 1 | sudo tee "/sys/bus/usb-serial/devices/${TTY##*/}/latency_timer"
```

## Build

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
cargo build --release --locked -p mstp-passive-sniff -p mstp-fec-diag -p mstp-mini-device
```

## Gate 2 — Passive (no TX)

Only one process may own the tty. Stop mini-device / fec-diag first.

```bash
cargo run --release -p mstp-passive-sniff -- \
  --serial "$PORT" --baud 38400 --seconds 60 \
  --report captures/mstp-passive-crc-fixed.json
```

PASS: `rx_bytes>0`, `tokens>0`, sources include **0 and 7**, `token_0_from_7>0`, Workbench stays online, **no Rust TX**.

## Gate 3 — Client-only FEC (after passive)

```bash
cargo run --release -p mstp-fec-diag -- \
  --serial "$PORT" --baud 38400 --mac 3 --max-master 7 --max-info-frames 1 \
  --device-instance 5007 --expect-mac 7 --ai-instance 1173 \
  --settle-ms 30000 --apdu-timeout-ms 15000 \
  --loop-secs 30 --loop-count 20 \
  --report captures/mstp-fec-ai1173-30s.json
```

Read-only. Never WriteProperty to the FEC. Start with AI:1173 (OA-T).

**Join tip:** Rust station `--max-master 7` (highest known master on this bench) so PollForMaster admits MAC 3 in tens of seconds. BASRT/FEC may keep Max_Master=127. Settle ≥30s; I-Am wait uses `--apdu-timeout-ms`.

## Gate 4 — Mini-device server-only

Stop fec-diag first. Then `mstp-mini-device` on MAC 3 / instance 123001; validate from Workbench/BASRT.

## Gates 5–6

Combined server+requester + FEC mirror + soak — see Phase 2 Rescue prompt / `PHASE_2_MSTP_MINI_DEVICE.md`. Not claimed PASS until evidence exists.

## rusty-bacnet pin

Workspace pins `bbartling/rusty-bacnet` @ `73a1fd4…` (Clause 9 CRC + USB stream + LOC split). Upstream PR: https://github.com/jscott3201/rusty-bacnet/pull/464 — re-pin to `jscott3201` when merged.
