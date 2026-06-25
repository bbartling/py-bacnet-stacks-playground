# Vibe12 build checkpoints (agent queue)

Pick **one** slice per mini wake. Critique (**gpt-5.5**) rewrites **Next for mini (ordered)** after each orchestrated wake.

## Human sign-off (required before production BACnet reads)

- [ ] I authorize BACnet RPM reads for devices listed in `edge_backup/.../points.csv`.
- [ ] IoT device policy allows `vibe12/.../telemetry` publish for this certificate.
- [ ] Cloud passwords are set in local `samconfig.toml` (never committed).

Signed off for **_(site / building)_**: _(date, initials)_.

## Current sprint

| Priority | Slice | Skill |
|----------|-------|-------|
| P0 | Edge telemetry → cloud ingest verified | `vibe12-ai-commissioning-api` |
| P1 | BRICK graph + canonical model | `vibe12-brick-data-model` |
| P2 | FDD rule test + go-live (human approves) | `vibe12-fdd-rule-lab` |

## Done recently

- _(UTC timestamp — one line per mini wake.)_

## Last critique (gpt-5.5)

- Date (UTC): _(critique pass writes this)_
- Summary: _(what changed, verification, risks)_
- **Next for mini (ordered):** _(see below — critique owns this list)_

## Next for mini (ordered)

1. Run `./scripts/validate_cloud_pipeline.sh`.
2. Fill `memo../edge_backup/PHASE_NOTEPAD.md` § A–D for your site.
3. Confirm commissioning API shows expected series count.
4. _(Critique adds 3–8 concrete tasks after each wake.)_

## Verification commands

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/validate_cloud_pipeline.sh
./scripts/verify_cloud_dashboard.sh
```
