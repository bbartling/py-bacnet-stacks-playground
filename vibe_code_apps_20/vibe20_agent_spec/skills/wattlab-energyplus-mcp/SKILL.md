---
name: wattlab-energyplus-mcp
description: >-
  Use when driving LBNL EnergyPlus-MCP or energyplus-mcp-dev Docker for WattLab
  twins: inspect/validate/modify/simulate IDF, capability_status, ReadVars CSV,
  DinD mounts. Triggers on: EnergyPlus-MCP, MCP tools, validate_idf, load_idf,
  energyplus-mcp-dev, simulate_only, full_mcp_available, eplusout.csv, -r.
---

# EnergyPlus-MCP — wrench, not calibration coach

LBNL EnergyPlus-MCP (~35 tools) is strong for **IDF surgery loops**: load,
validate, zones/surfaces/schedules/loads, HVAC topology, outputs, simulate,
plots, diagnostics. It will **not** decide TMY vs AMY, G14, or which FDD finding
to trust — WattLab + [`docs/SPARSE_BUILDING_PLAYBOOK.md`](../../docs/SPARSE_BUILDING_PLAYBOOK.md)
own that judgment.

DOE positions EnergyPlus as an **engine** third parties wrap. MCP is the access
layer; WattLab is the assumption + honesty framework.

## Capability modes

```python
from wattlab.energyplus.mcp import capability_status
print(capability_status())  # simulate_only | full_mcp_available | …
```

| Mode | Meaning |
| --- | --- |
| `full_mcp_available` | Vendor tree + image; inspect tools usable |
| `simulate_only` | Docker `energyplus-mcp-dev` sims OK; no interactive MCP |
| missing image | Build per `third_party/README.md` / `scripts/build_energyplus_mcp.sh` |

Studio GHCR image may be `simulate_only` until vendor MCP is mounted; host
checkout often has `full_mcp_available`.

## Campaign usage (required pattern)

1. **Simulate** via WattLab Docker (`wattlab easy-button` / `run_energyplus`).
   Default includes **`-r` (ReadVars)** → `eplusout.csv` for Twin 08 panes.
2. **Inspect** with MCP at least once per major IDF change: validate, zones,
   meters, run period, schedules/people/lights/equipment.
3. Prefer MCP modify tools for common knobs (people, lights, equipment,
   infiltration scale, …) when available; else WattLab IDF patches.
4. Publish every successful sim: `publish_run_for_studio` → `runs/<id>/`.

## DinD / Studio

When Studio runs in Docker with host docker.sock:

- Stage artifacts under `WATTLAB_STUDIO_WORKSPACE/.artifacts` (not `/app` only).
- Set `WATTLAB_HOST_WORKSPACE` to the host side of the `/data` bind so volume
  sources resolve on the daemon host.
- Set `WATTLAB_ROOT=/app` so prototypes resolve under `/app/examples/…`, not
  site-packages.

## What MCP does not cover (yet)

No first-class tools for: geometry synthesis from area/stories; code-baseline
generation; building-type default packs; tariff/emissions authoring; full HVAC
creation from narrative. Those belong in WattLab assumption engine + templates
— see [`wattlab-assumptions`](../wattlab-assumptions/SKILL.md).

## Hard rules

- No host `pyenergyplus` Runtime API.
- Demo replay ≠ Twin calibrate PASS.
- Log tool names used in `reports/CALIBRATE_SESSION.md`.
