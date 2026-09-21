---
name: diy-bacnet-router-two-pi
description: >-
  Resume or operate the isolated two-Pi BACnet/IP↔MS/TP lab for diy-bacnet-router
  (source G7/G8). Use when touching workerpi1/workerpi2, rusty-bacnet MS/TP pins,
  --route-enable, --mstp-qualify, --mstp-passive, Ansible lab units, Workbench
  remote net 2001 / device 123102, or daily upstream MS/TP watch. Companion to
  diy-bacnet-router AGENTS.md — not Vibe13 product Phase 3 work.
---

# DIY BACnet Router — two-Pi source lab

**Canonical product repo:** https://github.com/bbartling/diy-bacnet-router  
**Hold checkpoint (read first):** `docs/evidence/CHECKPOINT_2026-09-13_SOURCE_G7_G8_HOLD.md`  
**This playground:** Vibe13 `mstp-mini-device` is the **fixture only** (pin below). Do not expand Vibe13 Phase 3 as a substitute for the appliance.

Full brain dump for machine reformat: [reference-handoff-2026-09-13.md](reference-handoff-2026-09-13.md).

## Locked topology (do not invent)

```text
FX Workbench (any PC on 192.168.204.0/24)  B/IP net 1 UDP 47808
        |
workerpi1 192.168.204.59  diy-bacnet-router.service
  --route-enable --qualify-secs 0
  MS/TP net 2001 MAC 1  Waveshare C / FTDI BH002I9S
        |
  isolated RS-485 @ 38400  Max_Master=2  Max_Info_Frames=1
        |
workerpi2 192.168.204.60  mstp-mini-device.service
  MAC 2 device 123102  Waveshare B / CH343 5A98075745
```

| Rule | Value |
| --- | --- |
| MS/TP network | **2001** only — never **2000** (live BASRT) |
| Baud | **38400** unless evidence says otherwise |
| Serial | `/dev/serial/by-id/...` only |
| Tower x86 | Control plane / git / Ansible — **not** the BACnet router |
| Ordinary boot | Fail-closed (`router.enabled=false`); lab unlock = `--route-enable` |

## Pins at source G7/G8 evidence (2026-09-13)

| Pin | SHA |
| --- | --- |
| Router bench tip (evidence) | `2f97d57979a9cd4b255663786e3929f579ccbba7` |
| rusty-bacnet | `24e3439694b7d286e57e0a80cf7f1df4bd39d8ad` |
| Vibe13 fixture | `12e7d232b23023e1bb06da7b75972d79ca584cf9` |
| PR #64 merge on master | `56f27ef` |

Later tips (systemd / Ansible / docs) live on diy-bacnet-router `master` after PR #65 merges — re-read the checkpoint + `docs/UPSTREAM_LOCK.md`.

## Daily rusty-bacnet / MS/TP watch (mandatory)

Upstream https://github.com/jscott3201/rusty-bacnet enhances MS/TP **daily**. Every session:

1. Read pin in diy-bacnet-router `config/upstream-lock.toml` + `docs/UPSTREAM_LOCK.md`.
2. `git ls-remote` tip vs pin; note MS/TP / `mstp_frame` / serial / `bacnet-network` deltas.
3. Skim new PRs/issues for timing, token, CRC, stop/TTY ownership (affects issue [#66](https://github.com/bbartling/diy-bacnet-router/issues/66)).
4. **Never silently float the pin.** Bump only via audited lock PR + `--locked` suite.
5. Handoff must say: `upstream checked YYYY-MM-DD; pin still <sha>; [no|yes] MS/TP delta`.

Mirror of this policy: diy-bacnet-router `AGENTS.md` § Dependency policy.

## Source vs exact-image (claim discipline)

| Claim | Status (2026-09-13) |
| --- | --- |
| M2A B/IP netns G6 | PASS |
| M2B physical MS/TP **source** | PASS |
| M3 isolated routing **source** G7/G8 | PASS (Workbench saw 123102 / net 2001) |
| M3 exact-image / Buildroot G7/G8 | **OPEN** |
| M4–M6 / G9 USB stop ownership | **OPEN** |

Update README milestone **checkboxes** in the same PR as evidence. Checked M2B/M3 means **source** unless labeled exact-image.

## Operate the running lab

```bash
ssh ben@192.168.204.59 'systemctl status diy-bacnet-router --no-pager'
ssh ben@192.168.204.60 'systemctl status mstp-mini-device --no-pager'
```

Deploy (from diy-bacnet-router checkout):

```bash
ansible-playbook -i ansible/inventory/lab.yml ansible/playbooks/two_pi_lab.yml
# optional rebuild: -e rebuild_router=true -e rebuild_mini=true
```

Workbench: Discover → Remote **2001** → instance **123102**.  
UI tunnel: `ssh -N -L 18080:127.0.0.1:8080 ben@192.168.204.59` → http://127.0.0.1:18080

Wiring gate: isolated A+/B-/GND, ~60–70 Ω across bus, **no VCC**. Hard stop if wrong.

## Agent do / don't

**Do**

- Prefer diy-bacnet-router for router/web/routing; Vibe13 only for mini-device fixture.
- Use `--mstp-passive` (router-owned, fail-closed) before TX gates.
- Keep `--qualify-secs 0` for persistent lab (runs until SIGTERM).
- Record evidence under `docs/evidence/`; keep TESTING.md source vs image split honest.

**Don't**

- Claim Buildroot/exact-image PASS from Pi OS source runs.
- Kill unknown tty owners; share a serial port across processes.
- Treat Workbench `{fault,stale}` / timeout under MIF=1 + multi-point poll as Pi CPU starvation (lab was ~1.5% CPU / ~5 MiB RSS).
- Continue Vibe13 “Phase 3 product” as the appliance — that moved to diy-bacnet-router.

## Resume order after hold / new machine

1. Clone diy-bacnet-router + this playground; restore SSH to `.59` / `.60`.
2. Read checkpoint + SOURCE_G7_G8 evidence `result.md`.
3. Daily rusty-bacnet watch vs pin.
4. Confirm ohms, by-id serials, units active.
5. Workbench smoke Remote 2001 / 123102.
6. Next product gate: **exact-image G7/G8** on Buildroot — same topology/oracle.
