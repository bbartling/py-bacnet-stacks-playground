# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

---

## CRITIQUE UPDATE — 2026-05-15T16:30Z — Rough-in slice landed; stabilize

The human override slice has mostly landed in `/home/ben/bas_app`: `/rough-in/` is public, chat-first, table-based, read-only, simulator-only, and has server-side chat persistence. Do **not** restart the rebuild from scratch.

### Next priority

Use **`BUILD_CHECKPOINTS.md`** as the exact ordered queue. In short:

1. Polish remaining visual heaviness: radial background, shadows, large hero/card chrome, rounded pills, 12px radii. Keep the `graphic.html` dark token family, but make Phase 1 feel like utility tables, not a mini marketing dashboard.
2. Let the frontend networking table render the API contract rather than hardcoding most rows; keep 5173/tcp, 8000/tcp, and 47808/udp labeled honestly as simulator/no wire discovery.
3. Make persisted chat visible across wakes by documenting or mirroring the summary path; do not invent HVAC/BACnet site facts.
4. Add one narrow persistence smoke for POST then GET.

### Do NOT this wake

- Do not check acceptance roadmap `[x]` unless human field-verified.
- Do not expand skills; the prior wake already touched two existing skill topics.
- Do not add BACnet wire discovery.

### Verify

- `node --check frontend/rough-in/app.js`
- `python3 -m unittest backend.tests.test_app.BackendSmokeTests.test_public_rough_in_snapshot_is_available_without_auth backend.tests.test_app.BackendSmokeTests.test_public_rough_in_chat_posts_and_persists`
- `npm run build`
- `./scripts/smoke_public_rough_in.sh`
- Playwright rough-in smoke if UI/CSS changes substantially

---

## Older context (still valid where not superseded)

Graphics, auth, persistence, and operator shell at `http://<lan-ip>:5173/` remain the Phase 4 regression target. Simulator-first; public rough-in stays read-only.
