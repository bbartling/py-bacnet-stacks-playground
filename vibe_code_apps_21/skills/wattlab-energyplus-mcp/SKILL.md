---
name: wattlab-energyplus-mcp
description: >-
  Drive LBNL EnergyPlus-MCP / energyplus-mcp-dev for WattLab twins and ECM
  dial-in so sims match spreadsheet calcs. Use for ensure, mcp-exec, dial-loads,
  IDF inspect/modify/simulate, cascade DIVERGE fixes. Triggers on: EnergyPlus-MCP,
  energyplus-ensure, mcp-exec, dial-loads, energyplus-mcp-dev, eplusout.csv,
  ECM DIVERGE, spreadsheet vs E+.
---

# EnergyPlus-MCP — wrench for Twin + ECM ballpark

LBNL EnergyPlus-MCP (~35 tools) + Docker image `energyplus-mcp-dev` are the
**required** IDF surgery / sim layer. They do **not** choose G14 or ESCO policy —
WattLab skills own that. They **do** own making physics sims real when Compare
says `DIVERGE` or when adding ECM patches.

**Best practices:** `tools/BEST_PRACTICES_EPLUS_MCP_ECM.md`  
**Open-FDD MCP companion doc:** `open-fdd/docs/mcp-agents/companion-wattlab-energyplus.md`  
(`openfdd-mcp` = FDD only; this skill = E+ wrench.)

## Capability

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab energyplus-ensure
# capability_status → ready | image_missing | vendor_missing | unavailable
```

Agents **must** reach `ready` before claiming live ECM sims.

## Campaign usage

### Baseline Twin (G14)
1. Ensure → dial envelope/loads per `wattlab-twin-calibrate-dial`
2. MCP inspect after every major IDF change (`mcp-exec` / `dial-loads`)
3. Publish run + scorecard

### ECM spreadsheet ↔ E+ (required when enhancing sims)
1. Dump-tuned Inputs + agent Excel (`wattlab-agent-driven-ecm-excel`)
2. MCP **inspect** operator story in IDF (schedules, economizer, CHW, lockout)
3. Patch (registry or MCP modify) → `cascade-from-twin`
4. `compare_ecm_eplus_vs_spreadsheet.py`
5. If **DIVERGE**: prefer MCP dial toward dump-backed sheet hours, or fix Inputs if sheet used screening defaults — **never** silently scale E+ savings
6. Leave `NO_EP` honest until a patch exists

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab mcp-exec -- <tool args>

docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  wattlab notebook cascade-from-twin \
    --twin-run /data/runs/<g14_run> \
    --ecms ECM-CHILLER-LOCKOUT,ECM-AHU-SCHED-ALIGN,ECM-DSP-RESET,ECM-SAT-RESET

docker exec vibe20 python /data/tools/compare_ecm_eplus_vs_spreadsheet.py
```

## Hard rules

- No host `pyenergyplus` Runtime API — Docker / MCP only.
- Demo replay ≠ Twin calibrate PASS.
- Do not invent E+ kWh for measures without patches (`NO_EP`).
- Log MCP tools used in session notes / BUG_REPORT when dialing ECMs.
