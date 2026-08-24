# Shared Agent Skills Registry

Use these for new cross-project work unless an app's `AGENTS.md` explicitly routes to a frozen local skill.

| Skill | Purpose |
| --- | --- |
| [`energyplus-engineering`](energyplus-engineering/SKILL.md) | Umbrella routing for model inspection, edits, runs, evidence and claims |
| [`dataset-provenance`](dataset-provenance/SKILL.md) | Public dataset acquisition, hashes, raw/derived boundaries |
| [`energyplus-calibration`](energyplus-calibration/SKILL.md) | Existing-building calibration and Guideline-14 gates |
| [`utility-tariff`](utility-tariff/SKILL.md) | Historical tariff evidence and cost-model labels |
| [`dsm-experiment-design`](dsm-experiment-design/SKILL.md) | Reproducible DSM baseline/candidate comparisons |

## Migration posture

Do not bulk-delete the Vibe 19–22 local skills. They document the state of those experiments. Promote reusable concepts here incrementally, then let new apps reference this registry. Site-, model-, and experiment-specific procedures stay with the app that owns them.
