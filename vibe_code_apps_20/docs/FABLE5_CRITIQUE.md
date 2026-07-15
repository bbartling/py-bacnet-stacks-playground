# Fable 5 critique — vibe20 Sketchbox agent pack (2026-07-15)

Source: Claude Fable 5 thinking-high pass over pack + live drivers after the
three-building test drive. Stored here so agents can re-read without
re-running the review.

## Verdict

Governance (AGENTS.md, routing, policies, schemas) is strong — evidence hierarchy,
status vocabulary, secrets hygiene, and a Cursor skill that encodes live UI facts.
Live drivers still lag the constitution: integrity bugs around approval gates and
baseline contamination were the top finding; several are patched in the same
session (see "Patched after critique").

## What works well

- Secrets hygiene end-to-end; no invented public API
- Live-facts loop (ASCII hyphen, 5°F cool cap, `div.view-link[view=...]`)
- Status vocabulary partially used by testdrive
- Three climates produced distinct RESULT metrics after State/City set
- `INTEGRATION_PATCH_GUIDE.md` is an honest remaining-work list

## Gaps (original ranking)

| Rank | Issue |
| --- | --- |
| P0-1 | `draft` measures executed (must be `approved` only) |
| P0-2 | Offsets applied before "baseline" scrape; cross-building state bleed |
| P0-3 | `result_record.json` missing `run_id` / `input_hash` / `quality_flags`; `run_measure.py` ignores MeasureBrief |
| P1 | No read-back; no `--dry-run`; explore mutates; brittle RESULTS regex; duplicated selectors |
| P2 | Permissive schemas; dangling `interaction-analysis` route; unused `SKETCHBOX_HEADED`; no redaction |

## Skill OS

Routing table is the right shape; ~29 thin ECM skills are top-heavy — better as one
parameterized ECM skill + mapping table. Live selector facts lived in Cursor SKILL /
drivers, not in `selector-resilience` / `browser-operator` (partially addressed via
`sketchbox_ui.py` pointers).

## Recommended next 5 (original order)

1. approved-only + true baseline → measure sequencing
2. schema-valid ResultRecord + jsonschema tests
3. shared `sketchbox_ui.py` + selector map + HTML fixture tests
4. `--dry-run` / `--project-id` / `--artifact-dir`; make explore read-only
5. `run_measure.py` consumes approved MeasureBrief; fix routing dangling skill

## Patched after critique (this session)

- [x] approved-only gate
- [x] zero offsets → baseline scrape → apply measure → measure scrape
- [x] ResultRecord fields: `run_id`, `input_hash`, `quality_flags`, annual baseline/measure
- [x] `sketchbox_ui.py` shared helpers + read-back helper
- [x] `--dry-run` / `--artifact-dir` on testdrive
- [x] explore `try_tweak_schedule(mutate=False)` default
- [x] routing: drop nonexistent `interaction-analysis`
- [ ] MeasureBrief-driven `run_measure.py` (still open)
- [ ] jsonschema validation on emit (still open)
- [ ] HTML fixture selector tests (still open)
- [ ] redaction layer (still open)
