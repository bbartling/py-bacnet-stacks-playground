# BAS incremental build — checkpoints (Codex cron)

*(Automation backpedal 2026-05-15T16:20:02Z — wake logs archived, scheduler state cleared; human bare-bones UX override active. `bas_app` **not** deleted.)*

## Last critique (gpt-5.5)

- Date (UTC): 2026-05-15T16:30:12Z
- Critique summary: The wake appears to have landed the requested **bare-bones `/rough-in/` rebuild** in `/home/ben/bas_app`: public chat-first page, `GET/POST /api/public/rough-in`, JSON-backed server transcript, compact BACnet/network/device tables, dark/light toggle, smoke/docs/tests. Verified this pass: `node --check frontend/rough-in/app.js`, targeted backend rough-in tests, `./scripts/smoke_public_rough_in.sh`, `npm run build`, and `bas_skills_link.sh`. UI now uses the same dark slate / blue-green-red token family as `frontend_example/graphic.html`, but there is mild remaining drift from the human “bare bones” intent: hero/card chrome, radial background, shadows, rounded pills, and 12px radii still read more polished than plain utility tables. Skills changed in **two** existing topics (`field-commissioning-phases`, `web-app-bas`); they are small and aligned, but the next mini should avoid further skill expansion. Leave commissioning roadmap acceptance **`[ ]`** until human field-verifies Phase 1 / Day 0.
- **Next for mini (ordered):**
  1. Read **`GUARDRAILS.md`**, this checkpoint, **`next_directions.md`**, **`PHASE_NOTEPAD.md`**, and the rough-in files in `/home/ben/bas_app`; do **not** expand skills this wake unless a regression blocks retrieval.
  2. **Polish `/rough-in/` toward truly bare-bones:** remove radial background and heavy shadowing, reduce radii/chrome, keep simple neutral sections + plain tables, reserve color for status cells. Keep `graphic.html` dark token family for dark mode.
  3. Tighten the networking table contract: render API-provided listener/port rows instead of mostly hardcoded frontend rows; include the documented **5173/tcp**, **8000/tcp**, and **47808/udp simulator-only** rows plus any host observations without implying live BACnet discovery.
  4. Make persisted chat more wake-visible: either document the exact `runtime/rough_in_chat_summary.md` path in `PHASE_NOTEPAD.md` / README, or mirror a short summary into `bas_build_spec/memory/commissioning/` without inventing site context.
  5. Add/extend one narrow test or smoke that proves `POST /api/public/rough-in` persists and a subsequent `GET` returns the submitted message; keep it isolated with temp `BAS_COMMISSIONING_CHAT_PATH`.
  6. Run verification: `node --check frontend/rough-in/app.js`, `python3 -m unittest backend.tests.test_app.BackendSmokeTests.test_public_rough_in_snapshot_is_available_without_auth backend.tests.test_app.BackendSmokeTests.test_public_rough_in_chat_posts_and_persists`, `npm run build`, `./scripts/smoke_public_rough_in.sh`; run Playwright rough-in smoke if CSS/layout changes are substantial.
  7. Do **not** check Phase 1 / Day 0 acceptance **`[x]`** unless a human field-verifies the public route, no-login behavior, LAN/CORS docs, persisted chat, and no-write guarantee.

## Current sprint

- Primary: **Phase 1 rough-in stabilization after the bare-bones rebuild.** The core slice exists; next mini should reduce remaining visual chrome, tighten public snapshot/table contracts, and make persisted chat visible to future wakes. Keep **`http://<lan-ip>:5173/rough-in/`** public read-only (no login), operator shell at **`/`** for Phase 4, simulator-first, and no BACnet wire discovery.

## Done recently

- 2026-05-15T16:30:12Z — Critique verified the rough-in rebuild with syntax, targeted backend tests, public rough-in smoke, frontend build, and skill symlink refresh; queued small polish/contract tasks while leaving commissioning roadmap acceptance unchecked for field verification.
- 2026-05-15T16:27:00Z — Rebuilt `/rough-in/` into a chat-first public surface with server-persisted commissioning chat, a dark/light toggle, compact BACnet/network/device tables, and updated smoke/tests/docs for the slimmer snapshot.
- 2026-05-15T16:20:02Z — Automation backpedal: archived `cron_codex/logs/wake-*.log`, cleared `stop_mini_loop` / `DONE_AUTOMATION`, reset `cron/jobs-state.json` and `cron/runs/`; refreshed this checkpoint for bare-bones rebuild queue ( **`bas_app` kept** ).
- 2026-05-15 — Human override: simplify `/rough-in/` — bare-bones chat + tables, dark/light, persisted conversation (`spec.md`, `acceptance_criteria`, `next_directions.md`, skills).
