# Shared Agent Skills Registry

Use these for new cross-project work unless an app's `AGENTS.md` explicitly routes to a frozen local skill. Start with [`energyplus-engineering`](energyplus-engineering/SKILL.md) when the route is unclear.

| Area | Skills |
| --- | --- |
| Intake and data | [`building-intake`](building-intake/SKILL.md), [`dataset-provenance`](dataset-provenance/SKILL.md), [`evidence-and-measures`](evidence-and-measures/SKILL.md), [`openfdd-evidence-bridge`](openfdd-evidence-bridge/SKILL.md) |
| EnergyPlus | [`energyplus-model-authoring`](energyplus-model-authoring/SKILL.md), [`energyplus-weather`](energyplus-weather/SKILL.md), [`energyplus-calibration`](energyplus-calibration/SKILL.md), [`energyplus-mcp`](energyplus-mcp/SKILL.md), [`energyplus-results`](energyplus-results/SKILL.md) |
| ECM and economics | [`ecm-analysis`](ecm-analysis/SKILL.md), [`esco-bin-method`](esco-bin-method/SKILL.md), [`energy-economics`](energy-economics/SKILL.md), [`utility-tariff`](utility-tariff/SKILL.md) |
| Grid flexibility | [`energyplus-demand-management`](energyplus-demand-management/SKILL.md), [`dsm-experiment-design`](dsm-experiment-design/SKILL.md), [`grid-search-dsm`](grid-search-dsm/SKILL.md), [`policy-evaluation`](policy-evaluation/SKILL.md) |
| Publication | [`research-publication`](research-publication/SKILL.md), [`validation-and-release`](validation-and-release/SKILL.md) |

## Migration posture

The Vibe 19–22 local skills are preserved as historical experiment provenance. The shared tree now contains the reusable procedures extracted from their 56 discovered `SKILL.md` files. Site/model/campaign-specific paths, exact results, and explicitly invalid/archived processes remain local rather than becoming a generic instruction.

[`migration_registry.json`](migration_registry.json) is the machine-readable source-to-shared-skill map. Validate that no source was missed with:

```bash
python agentic_ai/skills/scripts/validate_registry.py
```
