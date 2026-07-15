# Implementation Roadmap

## P0 — Safe foundation
- Add typed domain schemas.
- Add artifact manifest and secret scanning.
- Add read-only UI discovery.
- Add robust baseline and result export tests.
- Create one golden project fixture with synthetic/anonymized data.

## P1 — Open-FDD bridge
- Ingest Vibe 19 `fdd_summary.csv`, session configuration, mappings, and analytics.
- Normalize rule IDs and equipment identities.
- Generate evidence records and candidate ECMs.
- Require human approval before measure execution.

## P2 — Initial ECM set
- Schedule reduction
- Economizer repair
- SAT reset
- Duct-static reset
- VAV minimum-flow reset
- Fan VFD/fan-power improvement
- Lighting power reduction
- Envelope/glazing scenarios
- Heating/cooling efficiency
- HVAC system switch

## P3 — Results and portfolio
- Export annual/monthly results.
- Reasonableness tests.
- Economics, emissions, and confidence-weighted ranking.
- Interaction notes and package analysis.

## P4 — Reporting and CI
- RCx narrative and tables.
- Browser contract tests against captured DOM fixtures.
- Nightly smoke test with no destructive actions.
- UI-change issue template with artifacts.
