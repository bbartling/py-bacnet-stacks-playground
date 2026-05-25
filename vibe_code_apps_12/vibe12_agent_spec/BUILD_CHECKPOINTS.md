# Vibe12 build checkpoints (agent queue)

Pick **one** slice per automated wake. Mark done in "Done recently" with UTC timestamp.

## Human sign-off (required before new sites)

- [ ] I authorize BACnet RPM reads for devices listed in `commissioning/.../points.csv` on this job.
- [ ] IoT device policy allows hierarchical `vibe12/.../telemetry` publish for this cert.
- [ ] Cloud `WebPassword` / `AuthSecret` are set in local `samconfig.toml` (not committed).

Signed off for **demo / bens-office**: lab bench 2026-05-25 (Pi scrape + cloud ingest verified).

## Current sprint

| Priority | Slice | Skill |
|----------|-------|-------|
| P0 | Keep telemetry flowing (6/6 series) | `vibe12-ai-commissioning-api` |
| P1 | BRICK graph + canonical model for demo building | `vibe12-brick-data-model` |
| P2 | FDD rule test + go-live for one ZAT rule | `vibe12-fdd-rule-lab` |
| P3 | Multi-series dashboard chart (MSTP + GPIO) | `apps/vibe12-web` |

## Done recently

- 2026-05-25 — Phase 0: IoT policy fixed; ingest BRICK refs; commissioning APIs; Pi 60 s → AWS; pcap easy button; agent spec scaffold.

## Last critique (gpt-5.5)

- Date (UTC): _(not run yet — use `/critique` in TUI or `vibe12_wake.sh`)_
- Summary: Phase 0 scaffold complete; telemetry 6/6; agent spec + APIs landed 2026-05-25.
- Verification: `./scripts/validate_cloud_pipeline.sh` OK at last human check.
- **Next for mini (ordered):** (critique rewrites this section each wake)

## Next for mini (ordered)

1. Run `./scripts/validate_cloud_pipeline.sh` and `ssh` Pi journal — confirm still 6/6 flowing.
2. `GET /api/brick/timeseries-ref/demo/bens-office` — ensure graph bootstrap matches registry.
3. Human: confirm ZAT points match job (MSTP STAT-ZN-T + GPIO BenOffice-ZAT).
4. Draft one FDD rule in Rule Lab; `POST /api/playground/test-rule` then go-live when human approves.
5. Read `cron_codex/state/context_since_last_wake.md` and `state/operator_notes.md` before changing bind or `points.csv`.
6. Append wake notes to `memory/YYYY-MM-DD.md`; promote deltas to `MEMORY.md`.

## Verification commands

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/validate_cloud_pipeline.sh
python3 -m unittest discover -s tests -q
cd apps/vibe12-web && npm test
```
