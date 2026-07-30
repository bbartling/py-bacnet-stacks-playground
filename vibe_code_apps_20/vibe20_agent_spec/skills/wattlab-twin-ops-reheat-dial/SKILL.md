---
name: wattlab-twin-ops-reheat-dial
description: >-
  As-operated Twin dial for dual-fuel G14: fan/OA runtime, DAT/reheat coupling,
  daytime HW (not plant kill), adaptive elec-first vs gas-first. Use when monthly
  ±% shows shape fail after envelope, gas spikes after cool DAT/long fans, or
  elec CV fails in peak cool months while gas is near pass. Triggers on: ops
  dial, reheat, HW availability, fan hours, 0% OA, daytime HW, elec-first G14,
  dual-fuel chess, tradeoff trap.
---

# WattLab Twin ops + reheat dial (Phase 2c)

**Start here:** [`../../docs/AGENT_CONTEXT.md`](../../docs/AGENT_CONTEXT.md).  
**Method SoT:** [`../../docs/BUG_REPORT_TWIN_DIAL_AI_CONTEXT.md`](../../docs/BUG_REPORT_TWIN_DIAL_AI_CONTEXT.md).  
**Envelope/SAT phases:** [`../wattlab-twin-calibrate-dial/SKILL.md`](../wattlab-twin-calibrate-dial/SKILL.md) +
[`../../docs/TWIN_DIAL_PLAYBOOK.md`](../../docs/TWIN_DIAL_PLAYBOOK.md) §2c.

EnergyPlus stays **autosize**. This skill is **schedules / setpoints / HW
availability by hour** — not more glass when the residual is ops-shaped.

## Gate (always)

Both fuels: `|NMBE| ≤ 5%` and `CVRMSE ≤ 15%`. Annual % alone ≠ calibrated.
Barely-≤15% CV is **provisional** — freeze after margin or stamp “edge pass.”
Never promote a run that flips a previously-passing fuel.

## Adaptive fuel order

Default envelope playbook is gas-then-elec. **Flip when monthly ±% says so:**

| Signal | Order |
|--------|--------|
| Elec long in shoulders / short in peak cool months | **Elec-first ops** (fans, OA, DAT), then gas recovery |
| Gas CV fail with elec already pass | **Gas-only knobs** (HW hours, winter fans, soft HW) — do not undo elec knobs |
| Both fail | One hypothesis per run; score **both** fuels every time |

## Elec-shape (as-operated)

| Symptom | Try |
|---------|-----|
| Shoulder elec **long** | Shorten AHU fan hours those months |
| Peak cool month elec **short** | Longer fans and/or cooler DAT and/or lower OA |
| Peak short + dump says recirc | **Fans on, OA ≈ 0** (even 24/7) |

## Gas recovery without killing elec

| Symptom | Try | Trap |
|---------|-----|------|
| Gas spike after cooler DAT / longer fans | **Daytime-only HW** in spike months | Full HW off → that month gas ≈ −100% vs bills |
| Still high gas | Soften HW OA-reset high SP; warm DAT slightly; shorten HW hours | Cooler DAT alone without HW control |
| Winter gas high | Shorter winter fan hours; softer HW | Cutting OA/fans can cut useful shoulder reheat |
| Shoulder gas short | Cooler DAT and/or higher VAV min those months | Raises chiller elec — watch elec CV |
| Near gas CV gate (~15–17) | Stack **small** knobs | One big plant-off usually overshoots |

## Reheat coupling (always state this)

```
more mechanical cooling (cool DAT, long fans, low OA)
  → more reheat opportunity
  → gas up unless HW is scheduled/softened
```

Dial **both sides** of the coil story in the same campaign narrative.

## FDD / dump → knob (no IDF surgery in openfdd-mcp)

1. Read monthly ±% (Studio dial charts) + dump DAT/fan/OA when present.
2. Form **one** schedule/HW hypothesis (not three knobs at once).
3. Patch + simulate via EnergyPlus-MCP / vibe20 tools — never invent savings.
4. Score both fuels; keep or revert if the other fuel flips.

Open-FDD agents: see `docs/mcp-agents/fdd-ops-to-twin-knobs.md` (pointer only).
