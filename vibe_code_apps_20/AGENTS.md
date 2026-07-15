# AGENTS.md — Vibe App 20 / Sketchbox

## Mission

Build a safe, auditable bridge from Open-FDD and Vibe App 19 analytics to conceptual Sketchbox ECM analysis. Optimize for engineering defensibility, reproducibility, and graceful recovery from UI changes.

## Mandatory reading order

1. `.agents/routing.md`
2. `.agents/policies.md`
3. `.agents/data_contract.md`
4. The selected skill's `SKILL.md`
5. The applicable checklist under `.agents/checklists/`
6. `docs/SKETCHBOX_KNOWLEDGE.md`
7. `docs/APP20_ARCHITECTURE.md`

## Hard rules

- Never commit `.env`, passwords, cookies, tokens, session storage, downloaded project archives, or customer data.
- Never claim Sketchbox has a public API.
- Never use browser selectors as the only record of a modeled input.
- Never overwrite an existing project without a saved export or explicit human approval.
- Never convert a fault directly into savings without a causal chain and applicability gate.
- Never bundle interacting ECMs while reporting them as independent savings.
- Never silently change a blue/default-derived Sketchbox value; record whether it was accepted, refreshed, or overridden.
- Never represent a specialized HVAC system as an exact match when Sketchbox only supports an approximation.
- Never publish utility savings or payback without listing rate, escalation, cost, and confidence assumptions.
- Never expose the actual building location in reports when the project is marked anonymized.
- Missing evidence produces `NEEDS_INPUT`, not invented values.
- UI automation failure must leave the project recoverable and produce artifacts explaining the last confirmed state.

## Standard statuses

- `READY`
- `NEEDS_INPUT`
- `NEEDS_ENGINEERING_REVIEW`
- `BLOCKED_UI_CHANGE`
- `BLOCKED_AUTH`
- `MODEL_RUN_FAILED`
- `RESULTS_SUSPECT`
- `COMPLETE`

## Required deliverables for every ECM

- Evidence record
- Applicability decision
- Baseline parameter(s)
- Proposed parameter(s)
- Sketchbox measure mapping
- Interaction notes
- Result record
- Confidence rating
- Human review disposition
- Report-ready narrative

## Definition of done

A task is complete only when:
1. inputs and assumptions are serialized;
2. the selected skill checklist passes;
3. artifacts exist for the last confirmed UI/model state;
4. results pass reasonableness checks;
5. limitations are reported;
6. tests and linting pass for changed code.
