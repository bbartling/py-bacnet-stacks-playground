# BAS incremental build — checkpoints (Codex cron)

*(Automation backpedal 2026-05-15T16:20:02Z — wake logs archived, scheduler state cleared; human bare-bones UX override active. `bas_app` **not** deleted.)*

## Last critique (gpt-5.5)

- Date (UTC): 2026-05-15T18:08:29Z
- Critique summary: The post-16:30 mini wakes mostly followed the queue: `/rough-in/` chrome was flattened further, `frontend/rough-in/app.js` now renders API-provided network rows, backend source now builds explicit Host / 5173 / 8000 / 47808 rows, README mentions the runtime chat store/summary, and the backend test proves POST-then-GET chat persistence. Verified this pass: `node --check frontend/rough-in/app.js`, targeted backend rough-in tests, `npm run build`, and `./scripts/smoke_public_rough_in.sh`. UI alignment is acceptable for the Phase 1 rough-in override: it keeps the `graphic.html` dark slate / blue-green-red tokens and is much more utilitarian, though pill status badges remain slightly more rounded than the strictest bare-table interpretation. Risks found: the currently running `:8000` process was stale and still served the older rough-in JSON without `networking.rows` / 47808 in `networking.listening`; Playwright could not run because `test-results/` is root-owned (`EACCES`) and the rough-in test expectation still appears out of sync with the newer row contract. Do not mark Phase 1 / Day 0 acceptance complete yet; the human has pasted real BACnet device/IP context and asked for polling, but real wire discovery still needs explicit lab-gated checkpoint sign-off.
- **Next for mini (ordered):**
  1. Read **`GUARDRAILS.md`**, this checkpoint, **`next_directions.md`**, **`PHASE_NOTEPAD.md`**, and `/home/ben/bas_app` rough-in files; do **not** expand skills this wake.
  2. Fix the stale runtime path: make `scripts/local_stack.sh start` detect source changes or dead/stale PIDs and restart `:8000` / `:5173` when needed; verify live `curl http://127.0.0.1:8000/api/public/rough-in` includes `networking.rows` and a 47808 simulator-only row after start.
  3. Tighten `scripts/smoke_public_rough_in.sh` so it asserts the API-rendered `networking.rows` contract includes **5173/tcp**, **8000/tcp**, and **47808/udp simulator-only**; do not treat 47808 as live BACnet discovery.
  4. Repair Playwright hygiene without using root-owned artifacts: either document/remove the root-owned `test-results/` blockage if permissions allow, or configure a user-writable output dir; update the rough-in test to match the current network row count/contract and rerun it.
  5. Mirror or summarize the persisted rough-in chat into **`PHASE_NOTEPAD.md`** or `bas_build_spec/memory/commissioning/` as operator-provided context only: VAV+AHU, VAV `192.168.204.14` / device `3456790`, AHU `192.168.204.113` / device `3456789`, BACnet bind candidate `192.168.204.18/24:47808` on `enp3s0`. Do **not** enable polling yet.
  6. Add a small UI/server status cue that real BACnet polling is **requested but gated**, with next step “human lab sign-off in BUILD_CHECKPOINTS” rather than silently leaving the request buried in chat.
  7. Run verification: `node --check frontend/rough-in/app.js`, targeted rough-in backend tests, `npm run build`, `./scripts/smoke_public_rough_in.sh`, live `curl` against `:8000`, and the Playwright rough-in smoke once the output-dir issue is fixed.
  8. Leave Phase 1 / Day 0 acceptance **`[ ]`** until human field-verifies public no-login LAN access, persisted chat, read-only behavior, CORS/LAN docs, and the no-wire-discovery guarantee.

## Current sprint

- Primary: **Phase 1 rough-in stabilization and lab-gate handoff.** The public rough-in page exists and is close to the bare-bones target; next mini should make the runtime restart path trustworthy, bring smoke/Playwright checks in line with the current network-row contract, surface the human-provided BACnet context in the notepad/memory, and keep real polling gated. Keep **`http://<lan-ip>:5173/rough-in/`** public read-only (no login), operator shell at **`/`** for Phase 4, simulator-first, and no BACnet wire discovery until a human explicitly signs off in this file.

## Done recently

- 2026-05-15T18:08:29Z — Critique verified rough-in source checks and found two blockers for the next mini: stale live `:8000` process serving old snapshot JSON, and root-owned Playwright `test-results/` preventing an E2E rerun. Acceptance roadmap remains unchecked pending human field verification and BACnet lab-gate sign-off.
- 2026-05-15T18:06:08Z — Flattened the rough-in UI chrome a little further by tightening radii/padding and making the primary action and chat fields more utilitarian while keeping the dark token family intact.
- 2026-05-15T16:42:00Z — Flattened the public rough-in chrome further toward utility-table styling by reducing hero/card shadowing, radii, padding, and pill prominence while keeping the dark token family intact.
- 2026-05-15T16:36:00Z — Tightened the public rough-in networking contract to surface API-provided rows for 5173/tcp, 8000/tcp, and 47808/udp simulator-only listeners, flattened the rough-in chrome a bit, documented the rough-in chat summary path, and added a GET-after-POST persistence assertion.
- 2026-05-15T16:30:12Z — Critique verified the rough-in rebuild with syntax, targeted backend tests, public rough-in smoke, frontend build, and skill symlink refresh; queued small polish/contract tasks while leaving commissioning roadmap acceptance unchecked for field verification.
- 2026-05-15T16:27:00Z — Rebuilt `/rough-in/` into a chat-first public surface with server-persisted commissioning chat, a dark/light toggle, compact BACnet/network/device tables, and updated smoke/tests/docs for the slimmer snapshot.
- 2026-05-15T16:20:02Z — Automation backpedal: archived `cron_codex/logs/wake-*.log`, cleared `stop_mini_loop` / `DONE_AUTOMATION`, reset `cron/jobs-state.json` and `cron/runs/`; refreshed this checkpoint for bare-bones rebuild queue ( **`bas_app` kept** ).
- 2026-05-15 — Human override: simplify `/rough-in/` — bare-bones chat + tables, dark/light, persisted conversation (`spec.md`, `acceptance_criteria`, `next_directions.md`, skills).
