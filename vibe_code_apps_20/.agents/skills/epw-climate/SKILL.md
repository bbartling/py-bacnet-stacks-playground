# Skill: epw-climate

Bind TMY3/EPW weather to the building profile climate.

## Rules

- Prefer a weather file matching city/state when available under `examples/weather/` or MCP samples.
- Madison WI → Chicago O'Hare TMY3 proxy is allowed for conceptual screens **only** with an explicit `epw_note`.
- Never silently swap climates between baseline and ECM runs in the same study.

## Related

`easy-button-calibrate`, `baseline-model`
