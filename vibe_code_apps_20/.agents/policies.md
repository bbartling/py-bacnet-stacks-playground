# Engineering and Automation Policies

## Evidence hierarchy

1. Verified design documents or equipment schedules
2. Calibrated BAS trends and meter data
3. Vibe 19/Open-FDD deterministic outputs
4. Site observations and operator interviews
5. Utility bills
6. Engineering inference
7. Sketchbox defaults
8. Generic rule of thumb

Never promote a lower tier above a conflicting higher tier without written justification.

## Confidence

- **High:** direct documented or measured input; causal chain verified.
- **Medium:** strong inference with complete prerequisites.
- **Low:** conceptual screening assumption or incomplete operational evidence.
- **Rejected:** contradictory, physically implausible, or unsupported.

## Browser automation

- Prefer role, label, and stable semantic selectors.
- Use text selectors only with page-context checks.
- Avoid brittle nth-child and generated class selectors.
- Capture a screenshot and structured state summary before and after every write.
- Verify the written value by reading it back.
- Save/export after milestone transitions.
- On unexpected UI, stop and classify `BLOCKED_UI_CHANGE`.

## Legal and product boundaries

This package is an independent workflow aid. Do not imply affiliation with or endorsement by Slipstream. Respect account terms, rate limits, and access controls.
