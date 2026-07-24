---
name: wattlab-energyplus-mcp
description: >-
  Use when driving LBNL EnergyPlus-MCP or energyplus-mcp-dev Docker for WattLab
  twins: ensure, inspect/validate/modify/simulate IDF, capability_status,
  eplusout.csv, -r. Triggers on: EnergyPlus-MCP, MCP tools, energyplus-ensure,
  mcp-exec, dial-loads, energyplus-mcp-dev, ready, eplusout.csv.
---

# EnergyPlus-MCP — wrench, not calibration coach

LBNL EnergyPlus-MCP (~35 tools) is strong for **IDF surgery loops**: load,
validate, zones/surfaces/schedules/loads, HVAC topology, outputs, simulate,
plots, diagnostics. It will **not** decide TMY vs AMY, G14, or which FDD finding
to trust — WattLab + [`docs/SPARSE_BUILDING_PLAYBOOK.md`](../../docs/SPARSE_BUILDING_PLAYBOOK.md)
own that judgment. For **short/long fuel** dial order (WWR / U / ACH → LPD/EPD →
banded SAT), see [`wattlab-twin-calibrate-dial`](../wattlab-twin-calibrate-dial/SKILL.md)
and [`docs/TWIN_DIAL_PLAYBOOK.md`](../../docs/TWIN_DIAL_PLAYBOOK.md) — MCP patches
the IDF; the playbook chooses which knobs.

DOE positions EnergyPlus as an **engine** third parties wrap. MCP is the access
layer; WattLab is the assumption + honesty framework.

## Capability modes

```python
from wattlab.energyplus.mcp import capability_status
print(capability_status())  # ready | image_missing | vendor_missing | unavailable
```

| Mode | Meaning |
| --- | --- |
| `ready` | Image + vendor — DinD sims **and** mcp-exec/dial-loads surgery |
| `image_missing` | Vendor OK; run `wattlab energyplus-ensure` to build |
| `vendor_missing` | Image OK; run ensure to clone under `/data/third_party/EnergyPlus-MCP` |
| `unavailable` | No Docker / nothing present — ensure after sock + host workspace |

**Required:** agents call `wattlab energyplus-ensure` until `capability == ready`.
There is no supported “simulate only” soak path.

## Campaign usage (required pattern)

1. **Ensure** once: `wattlab energyplus-ensure`
2. **Simulate** via WattLab Docker (`wattlab easy-button` / `run_energyplus`).
   Default includes **`-r` (ReadVars)** → `eplusout.csv` for Twin 08 panes.
3. **Inspect/modify** with MCP for every major IDF change: zones, meters,
   people/lights/equipment, infiltration — `wattlab dial-loads` or
   `wattlab mcp-exec -- …`.
4. Publish every successful sim: `publish_run_for_studio` → `runs/<id>/`.

## DinD / Studio

When Studio runs in Docker with host docker.sock:

- Annual sim: WattLab mounts stage dirs into `energyplus-mcp-dev`
- MCP surgery: `mcp-exec` mounts `$WATTLAB_HOST_WORKSPACE→/data` + vendor→`/workspace`
- Vendor lives on the **shared workspace**, not inside the vibe20 GHCR tip image

Cursor interactive MCP: see `third_party/README.md` / `cursor_mcp_config_snippet()`.
