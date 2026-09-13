# Brain dump — 2026-09-13 (tower reformat imminent)

**Audience:** next agent / Ben after this x86 tower is wiped.  
**Repos:** source BIP↔physical MS/TP **PASS**; lab left **enabled + active** on both Pis; product pause is OK. Exact-image still OPEN.

## Repos and remotes

| Repo | Remote | Notes |
| --- | --- | --- |
| diy-bacnet-router | `https://github.com/bbartling/diy-bacnet-router.git` | Product appliance |
| py-bacnet-stacks-playground | `https://github.com/bbartling/py-bacnet-stacks-playground.git` | Vibe apps; mini-device fixture |
| rusty-bacnet (upstream) | `https://github.com/jscott3201/rusty-bacnet` | Pin only; enhance daily — watch |

### diy-bacnet-router branch / PR state at dump time

- **Merged:** PR [#64](https://github.com/bbartling/diy-bacnet-router/pull/64) — `--mstp-passive --expect-source N`, SOURCE_G7_G8 evidence, testing/README source vs image.
- **Open (merge when CI green):** PR [#65](https://github.com/bbartling/diy-bacnet-router/pull/65) `feat/lab-persist-systemd-ansible` — `--qualify-secs 0`, `ansible/`, hold checkpoint, Workbench/hardware photos, README milestone checkboxes, AGENTS daily rusty-bacnet watch, UPSTREAM_LOCK pointer.
- Tip on that branch at dump: includes commits through `0e53780` (UPSTREAM_LOCK daily-watch pointer). Tip may move — `gh pr view 65`.
- CodeRabbit on #65: **skipped** (manual review required for OSS) — no actionable comments.
- Issue [#66](https://github.com/bbartling/diy-bacnet-router/issues/66): FEC-feel / Workbench timeouts vs Pi resources follow-up (baud 38400; Pi load light).

### playground branch / PR state

- Open PR [#162](https://github.com/bbartling/py-bacnet-stacks-playground/pull/162) `feat/vibe24-eplus-thermostat-sim` — EnergyPlus thermostat sim + notebooks; **this skill dump commits here**.
- Local dirty often: `vibe_code_apps_16/openfdd-bacnet-mimic/Cargo.lock` — do **not** commit unless intentional.
- Vibe13 fixture SHA for lab: `12e7d232b23023e1bb06da7b75972d79ca584cf9`.
- Historical Vibe13 wiring ohms doc branch: `docs/vibe13-pi-lab-wiring-ohms` (C↔B ~127/127/~71 Ω unpowered).

## Lab hosts (survive reformat — Pis stay)

| Host | IP | Role | Unit |
| --- | --- | --- | --- |
| workerpi1 | `192.168.204.59` | Router | `diy-bacnet-router.service` |
| workerpi2 | `192.168.204.60` | Mini-device | `mstp-mini-device.service` |
| User | `ben` | SSH + passwordless sudo expected | |

**Serial by-id (from ansible inventory)**

- pi1: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0` (Waveshare C)
- pi2: `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A98075745-if00` (Waveshare B / CH343)

**Paths on Pis (as deployed)**

- Router src: `/home/ben/src/diy-bacnet-router`
- Config: `/home/ben/lab/dbr-two-pi.toml`
- Playground/Vibe13 src: `/home/ben/src/py-bacnet-stacks-playground`
- Management: `127.0.0.1:8080` on pi1 only
- BACnet UDP: `47808` on pi1 eth0

**At dump time:** both units reported `active` via SSH.

## What was proven (source vertical slice)

1. Preflight: aarch64, eth0, by-id serial, dialout, UDP 47808 free.
2. Passive RX / join: token to MAC 2, `--mstp-qualify` then TTY release.
3. `--route-enable`: I-Am-Router; Who-Is → I-Am SNET 2001 SADR 02; ReadProperty ComplexACK (Object_Name + AI:1 ~1–4).
4. FX Workbench from another PC discovered **Rust MS/TP Mini Device** on remote **2001**.
5. Evidence pack: `diy-bacnet-router/docs/evidence/SOURCE_G7_G8_TWO_PI_20260913T175327Z_2f97d57979a9/`
6. Hold/resume: `docs/evidence/CHECKPOINT_2026-09-13_SOURCE_G7_G8_HOLD.md`

## Key product flags / semantics

| Flag / knob | Meaning |
| --- | --- |
| `router.enabled=false` | Ordinary / fail-closed |
| `--route-enable` | Lab unlock forwarding |
| `--qualify-secs N` | Finite management exit when N>0 |
| `--qualify-secs 0` | Run until SIGTERM (persistent lab) |
| `--mstp-qualify` | Join-only qualify then release |
| `--mstp-passive --expect-source N` | RX-only stream decode; fail-closed |

## Docs agents must keep honest

In **diy-bacnet-router** (not only this skill):

- `README.md` Milestones — source checkboxes vs exact-image open boxes
- `AGENTS.md` — Spec table + **Daily rusty-bacnet / MS/TP watch**
- `docs/TESTING.md` — G0–G11 ledger; source vs exact-image
- `docs/UPSTREAM_LOCK.md` + `config/upstream-lock.toml`
- `ansible/README.md` + `ansible/inventory/lab.yml`

## Explicitly still OPEN

- Exact-image / Buildroot G7/G8 (same topology + oracle)
- G9 USB/serial stop ownership (`BACnetRouter::stop()` / TTY)
- BBMD/FDR, extended frames, segmentation, BTL
- Forwarding counters / dashboard BACnet proof-quality metrics
- Treating Workbench multi-point poll timeouts as “fixed” without FEC-parity work (#66)

## Next agent checklist (new machine)

1. Reinstall SSH keys; confirm `ping 192.168.204.59` / `.60`.
2. `git clone` both repos; checkout diy-bacnet-router `master` (or finish merging #65).
3. Read checkpoint + this skill.
4. Run **daily rusty-bacnet watch** vs pin `24e3439…`.
5. `systemctl is-active` both units; Workbench Remote 2001 / 123102.
6. If tower was the only place with unpushed work: verify GitHub has #65 tip + this `agentic_ai` skill commit.
7. Product next: Buildroot exact-image G7/G8 — **not** more Vibe13 appliance feature work.

## Stop lab before long power-off

```bash
ssh ben@192.168.204.59 'sudo systemctl disable --now diy-bacnet-router'
ssh ben@192.168.204.60 'sudo systemctl disable --now mstp-mini-device'
```

## Related chat / plan (local only — may die with reformat)

- Plan: `~/.cursor/plans/two-pi_bacnet_source_e9f50d43.plan.md`
- Transcript UUID: `403deecf-ddc7-48a4-973d-69df8a8d9db0`

Prefer GitHub evidence + this skill over local Cursor plan files after wipe.

## Open-FDD / other (tangential)

Recent local read: `~/open-fdd/docs/operations/BUG_REPORT_OT_MODBUS_HAYSTACK.md` — separate from two-Pi BACnet. Do not conflate.

## EnergyPlus / Vibe24

Playground PR #162 carries EnergyPlus plant + thermostat SP/deadband + live sim speed. Shared EnergyPlus skills remain under `agentic_ai/skills/energyplus-*`. Use those for sim work; use **this** skill for BACnet two-Pi lab.
