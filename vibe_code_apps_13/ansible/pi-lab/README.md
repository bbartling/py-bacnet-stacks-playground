# Vibe13 Ansible Pi lab (workerpi1 / workerpi2)

Isolated B+C MS/TP regression lab controlled from the Ubuntu tower (bensbench).
**The tower's live Waveshare C / mini-device / FEC trunk are not Ansible targets.**

## Quick start

```bash
cd vibe_code_apps_13/ansible/pi-lab
python3 -m venv .venv
.venv/bin/pip install -r requirements-controller.txt
.venv/bin/ansible-galaxy collection install -r requirements.yml
# Optional for --ask-pass: sudo apt install sshpass
cp inventory.example.yml inventory.local.yml
chmod +x scripts/pi-lab scripts/build_release.sh

./scripts/pi-lab preflight
./scripts/pi-lab bootstrap          # reuses tower key already on Pis
./scripts/pi-lab discover
```

Password path (optional; never store the secret):

```bash
./scripts/pi-lab preflight --ask-pass
./scripts/pi-lab bootstrap --ask-pass --ask-become-pass
```

## Seeded adapters (2026-09-04)

| Host | IP | Model | by-id |
|------|-----|-------|-------|
| workerpi1 | 192.168.204.59 | Waveshare B (FTDI) | `usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0` |
| workerpi2 | 192.168.204.60 | Waveshare C (CH343) | `usb-1a86_USB_Single_Serial_5A98075745-if00` |

## Physical gate (required before TX)

Wire **only** the two Pi adapters to each other. Then:

```bash
./scripts/pi-lab confirm-wiring --confirmed
./scripts/pi-lab build --revision <FULL_SHA>
./scripts/pi-lab deploy --revision <FULL_SHA>
./scripts/pi-lab run --profile raw-wire --pair bc
./scripts/pi-lab run --profile mstp-smoke --pair bc
```

## Observer tunnels (from Windows after host-key setup)

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 ben@192.168.204.59
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8766:127.0.0.1:8765 ben@192.168.204.60
```

## Recovery / troubleshooting

- `preflight` fails on allowlist → inventory drifted from `.59`/`.60`.
- Discover missing by-id → replug USB; do not guess `ttyUSB0`.
- Deploy refuses without `files/releases/<sha>` → run `build` on tower/CI.
- Never `fuser -k` / killall on the tower.

Upstream pin: `af4e88680c51eb4da64dac47f0540a35bf184732` (distinct from app release SHA).
