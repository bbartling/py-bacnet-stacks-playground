---
name: policy-evaluation
description: Evaluate frozen DSM or RL policies with continuous EnergyPlus trajectories, consistent observations, readiness metrics, and publication-safe comparisons.
---

# Policy evaluation

Use for frozen-policy replay, RL validation, or reporting campaign outcomes.

- Separate training reward from constrained evaluation cost. Training mean reward is not a validation leader.
- Use the same complete observation schema and action interpretation used by the saved policy; do not substitute zero/default observations without labeling a diagnostic.
- Freeze initial state, weather, calendar, baseline, tariff contract, and policy artifact. Record process starts/continuity and artifact hashes.
- Publish checked readiness days separately from non-applicable days; never turn auto-pass days into comfort success.
- Do not compare absolute dollars across different tariff definitions or score a utility invoice against an illustrative tariff reconstruction.
- Preserve raw manifests. Report only provenance-backed counters and label simulation-only work as non-operational.

Use `grid-search-dsm` for transparent discrete comparators and `energyplus-results` for physical metrics.
