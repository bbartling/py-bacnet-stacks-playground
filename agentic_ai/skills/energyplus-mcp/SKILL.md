---
name: energyplus-mcp
description: Use an available EnergyPlus MCP integration for IDF inspection, validation, simulation, and artifact discovery; it is not a substitute for engineering evidence or calibration.
---

# EnergyPlus MCP

Use the configured integration to inspect model topology, validate IDFs, make controlled edits, run simulations, and inspect outputs. Before invoking it, record the model and weather inputs; afterward, record the tool/runtime version, command/action, artifacts, and changes.

MCP capability is environment-specific. Confirm supported operations rather than assuming it can author complete sequence logic, reproduce a host installation, or establish calibration. Route model decisions through `energyplus-model-authoring` and `energyplus-calibration`.
