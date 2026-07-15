# Task Router

Route work by intent. Load only the minimum necessary skills.

| Intent | Primary skill | Supporting skills |
|---|---|---|
| Inspect repository or UI | `sketchbox-ui-exploration` | `artifact-capture`, `selector-resilience` |
| Build baseline | `baseline-model` | `building-intake`, `shell-geometry`, `schedules`, `hvac-mapping` |
| Convert Vibe 19 outputs | `openfdd-bridge` | `evidence-normalization`, relevant ECM skill |
| Create/run measure | `measure-authoring` | relevant ECM skill, `browser-operator` |
| Parse savings | `results-extraction` | `results-qa`, `economics-carbon` |
| Rank ECMs | `ecm-portfolio` | `economics-carbon`, `results-qa` |
| Generate RCx report | `report-writer` | `anonymization`, `results-qa` |
| Repair automation | `selector-resilience` | `sketchbox-ui-exploration`, `artifact-capture` |
| Test code | `testing-validation` | relevant implementation skill |

## Routing sequence

1. Identify whether the task changes code, a model, or both.
2. Determine whether the project is anonymized.
3. Determine whether the baseline is approved.
4. Identify the evidence class: measured, documented, inferred, default, or unknown.
5. Select exactly one primary skill.
6. Add supporting skills only when required.
7. Run the readiness checklist before browser actions.
8. Stop on ambiguity that materially changes savings or system representation.
