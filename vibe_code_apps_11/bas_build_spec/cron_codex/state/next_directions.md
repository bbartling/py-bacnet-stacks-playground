# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

---

## CRITIQUE UPDATE — 2026-05-15T18:08Z — Runtime + lab-gate cleanup

The human override slice has landed and has been polished: `/rough-in/` is public, chat-first, table-based, read-only, simulator-only, dark/light, and has server-side chat persistence. Do **not** restart the rebuild from scratch.

The human pasted real lab context into the rough-in chat:

- VAV+AHU system.
- VAV at `192.168.204.14`, BACnet device `3456790`.
- AHU at `192.168.204.113`, BACnet device `3456789`.
- Candidate BACnet bind is `192.168.204.18/24:47808` on `enp3s0`.

Treat that as operator-provided context, not verified discovery. Real BACnet polling remains gated by `GUARDRAILS.md` / `bacnet-driver-lifecycle`: no wire discovery or writes until a human records explicit lab sign-off in `BUILD_CHECKPOINTS.md`.

### Next priority

Use **`BUILD_CHECKPOINTS.md`** as the exact ordered queue. In short:

1. Fix stale runtime behavior so `local_stack.sh start` does not keep serving old backend code after source changes.
2. Tighten the public rough-in smoke around the current `networking.rows` contract: 5173/tcp, 8000/tcp, and 47808/udp simulator-only.
3. Fix Playwright output hygiene; `test-results/` is currently root-owned and blocks reruns with `EACCES`.
4. Update the rough-in Playwright expectation to match the current API row contract, then rerun the rough-in smoke.
5. Mirror/summarize the pasted lab context into `PHASE_NOTEPAD.md` or `bas_build_spec/memory/commissioning/` without enabling polling.
6. Surface “BACnet polling requested but gated” in the UI/API or notepad so the request is visible across wakes.

### Do NOT this wake

- Do not check acceptance roadmap `[x]` unless human field-verified.
- Do not expand skills; the prior wake already touched two existing skill topics.
- Do not add BACnet wire discovery or BACnet writes.

### Verify

- `node --check frontend/rough-in/app.js`
- `python3 -m unittest backend.tests.test_app.BackendSmokeTests.test_public_rough_in_snapshot_is_available_without_auth backend.tests.test_app.BackendSmokeTests.test_public_rough_in_chat_posts_and_persists`
- `npm run build`
- `./scripts/smoke_public_rough_in.sh`
- live `curl -fsS http://127.0.0.1:8000/api/public/rough-in`
- Playwright rough-in smoke after fixing the user-writable output-dir issue

---

## Older context (still valid where not superseded)

Graphics, auth, persistence, and operator shell at `http://<lan-ip>:5173/` remain the Phase 4 regression target. Simulator-first; public rough-in stays read-only.
