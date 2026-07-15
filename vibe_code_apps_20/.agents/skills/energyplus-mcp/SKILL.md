# Skill: energyplus-mcp

Drive the LBNL EnergyPlus-MCP Docker toolkit (`energyplus-mcp-dev`).

## Use when

- Loading / validating / inspecting IDF models
- Running simulations with EPW
- Plotting outputs or discovering HVAC topology
- Checking server / EnergyPlus version status

## Do not claim

- Full ASHRAE Guideline 36 authoring via MCP modify tools
- Host EnergyPlus without Docker for this app

## Commands / surfaces

- Cursor MCP config: `third_party/README.md`
- App mirrors: `ep_mcp_client.py`, `ep_docker.py`
- Pin: `third_party/VERSION.txt` (EP 26.1)

## Outputs

Tool results, plots under `.artifacts/`, and notes of any `NEEDS_INPUT`.
