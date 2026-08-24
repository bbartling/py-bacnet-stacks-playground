---
name: evidence-and-measures
description: Normalize building evidence and author reviewable EnergyPlus or controls measure definitions without hiding assumptions or interacting changes.
---

# Evidence and measures

Use this for BAS findings, source documents, ECMs, or model changes derived from evidence.

- Normalize units, timestamps, and interval semantics; deduplicate overlapping observations before aggregating fault/runtime hours.
- Keep observation separate from interpretation. Give immutable evidence IDs, source links, confidence, and equipment identity.
- Before changing an IDF, author one measure brief per coherent intervention: mechanism, applicability gate, exact baseline/proposed values and units, provenance, implementation notes, interactions, and limitations.
- Do not combine multiple control changes behind a vague measure title or add individual ECM savings as a package result without an explicitly simulated package.
- Treat Guideline 36 and other sequence proxies as conceptual unless the actual sequence is modeled and verified.

Use `building-intake` for the profile and `energyplus-results` for output checks.
