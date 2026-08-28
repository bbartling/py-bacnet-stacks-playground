# Phase 1 cheat sheet — dual USB RS-485 on this tower

**Agent USB check (2026-08-28):** Both Waveshare **C** / FT232 adapters enumerated on front USB (`BH002I9S` → `ttyUSB0`, `BH001FQ0` → `ttyUSB1`). **100-round C+C hardware smoke PASS** (`captures/wire-test-smoke.json`). Phase 1 **10k gate** still pending.

**You need once:** `sudo usermod -aG dialout $USER` then **log out/in** or `newgrp dialout` before opening serial ports.

---

## 1. Wire (power off / USB unplugged while changing terminals)

```text
                    Ubuntu tower
   front USB #1 ──► Waveshare C  "A"          Waveshare C  "B"  ◄── front USB #2
                         │                           │
                        A+ ═════════════════════════ A+
                        B- ═════════════════════════ B-
                   GND/REF ═════════════════════════ GND/REF
                     (120 Ω onboard)           (120 Ω onboard)
```

| Do | Don't |
|----|-------|
| A+→A+, B-→B-, field GND/REF→GND/REF | Connect 5V / VCC between adapters |
| Labels on the terminal block, not wire color | Star / Y splices |
| Short daisy-chain; adapters = two ends | Extra 120 Ω if both already terminated |
| Measure A↔B cold ≈ **60 Ω** (two 120s parallel) | Join chassis / PE / USB grounds to “fix” RS-485 |

Waveshare **C** = FT232RNL, auto direction, usually `ttyUSB*`. Keep **B** (CH343) for later B+B / B+C — not for first baseline.

Prefer **two front USB ports** for the first run (easy unplug/replug map). Motherboard rear ports are fine; if by-id serials collide, park each stick in a fixed rear port and alias by USB path.

---

## 2. Identify after plug-in

```bash
lsusb
ls -l /dev/serial/by-id/
find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -ls
```

Map physical A/B: unplug only B → note which `by-id` vanishes → plug back. **Never** hard-code `ttyUSB0` in config.

```bash
# optional: who owns the port
sudo lsof /dev/ttyUSB0   # use real nodes
# FTDI C only:
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
```

Record in a sticky note:

```text
A: /dev/serial/by-id/usb-...   (label tape "A")
B: /dev/serial/by-id/usb-...   (label tape "B")
```

---

## 3. Host prep

```bash
sudo apt-get install --yes build-essential pkg-config libudev-dev usbutils lsof
sudo usermod -aG dialout "$USER"   # then re-login; verify: id | grep dialout
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
cargo test --workspace
cargo build --release -p serial-wire-test
```

---

## 4. Run Phase 1 (after both sticks wired + by-id known)

Smoke (100 rounds):

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
RUST_LOG=info cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_A \
  --port-b /dev/serial/by-id/REPLACE_B \
  --baud 38400 --rounds 100 --max-payload 256 \
  --report captures/wire-test-smoke.json
```

Gate (10 000 rounds @ 38 400):

```bash
RUST_LOG=info cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/REPLACE_A \
  --port-b /dev/serial/by-id/REPLACE_B \
  --baud 38400 --rounds 10000 --max-payload 256 \
  --seed 1337 \
  --report captures/wire-test-38400.json
```

Unplug fault: start a 100-round run, yank **B** mid-flight → must exit nonzero with a failed JSON report, no hang.

Pass = zero missing / corrupt / duplicate **peer** frames; local echo counted separately OK.

---

## 5. What this is / isn’t

| This proves | This does not prove |
|-------------|---------------------|
| Two USB paths + FTDI + A/B wire + auto-dir | Long trunk, noise, bias correctness in the field |
| Raw bidirectional bytes @ 8N1 | BACnet / MS/TP / token / router |

Do **not** start Phase 2 until the 10k report is green.
