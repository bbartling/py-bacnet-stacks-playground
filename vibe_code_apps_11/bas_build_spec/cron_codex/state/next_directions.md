# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

## 2026-05-11 critique handoff

The next mini should keep the slice narrow: make schedules real enough to persist and audit before moving to commands or historian work. The React widget already emits useful weekly JSON, so avoid rebuilding the interaction. Add backend schedule list/get/update routes, save the selected equipment schedule from the UI, show dirty/saved/error state, and record schedule edits in a simple audit store.

Verification to record in `BUILD_CHECKPOINTS.md` and `memory/2026-05-11.md`: `npm run build`, backend `/health`, one schedule API smoke, frontend `5173`, warning-or-higher `journalctl --user` for both units, and `bas_validate_automation.sh`.

Do not run BACnet discovery unless `BAS_BACNET_LAB_VERIFY=true` and the bind env is configured. Do not create `CODEX_ACCEPTANCE_COMPLETE`; the release gate is still incomplete.
