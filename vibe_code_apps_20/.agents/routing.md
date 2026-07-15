# Task Router — OpenFDD WattLab

Route work by intent. Load only the minimum necessary skills.

| Intent | Primary skill | Supporting skills |
|---|---|---|
| Run easy-button screen | `easy-button-calibrate` | `energyplus-mcp`, `epw-climate`, `idf-patching` |
| Use full EnergyPlus-MCP toolkit | `energyplus-mcp` | `baseline-model`, `results-extraction` |
| Build / freeze baseline IDF | `baseline-model` | `building-intake`, `hvac-mapping`, `epw-climate` |
| Convert Vibe 19 / OpenFDD outputs | `openfdd-bridge` | `evidence-normalization`, relevant ECM skill |
| Author MeasureBrief | `measure-authoring` | `idf-patching`, relevant ECM skill |
| Guideline 36 / GL36 airside screen | `gl36-airside` | `schedule-optimization`, `vav-minimum-reset`, `idf-patching` |
| Schedule ECMs | `schedule-optimization` | `idf-patching`, `openfdd-bridge` |
| Parse savings | `results-extraction` | `results-qa`, `economics-carbon` |
| Rank ECMs | `ecm-portfolio` | `economics-carbon`, `results-qa` |
| Generate RCx report | `report-writer` | `anonymization`, `results-qa` |
| Test / verify Docker path | `testing-validation` | `energyplus-mcp` |

## Routing sequence

1. Identify whether the task changes code, a model, or both.
2. Determine whether the project is anonymized.
3. Determine whether the baseline is approved.
4. Identify the evidence class: measured, documented, inferred, default, or unknown.
5. Select exactly one primary skill.
6. Add supporting skills only when required.
7. Prefer **easy button** for progressive ECM screens; use **EnergyPlus-MCP** for deep inspect/plot/validate.
8. Stop on ambiguity that materially changes savings or system representation.
