# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

*(Reset 2026-05-13T16:33:18Z — bas_redo_automation_state.sh.)*

## 2026-05-14 post-graphics context

The graphics pass is now verified for the seeded program: AHU-1 primary synoptic, VAV-101 terminal/zone slice, Lighting Panel L1 secondary/ancillary slice, simulator-backed live polling, deep links, and a graphic command entry into the existing pt-2 workflow all pass the Playwright smoke. Do not repeat that work unless fixing regressions.

The 03:00Z wake closed browser alarm ack/shelve coverage, safe CORS defaults, and a tiny audited Engineer/Admin point metadata edit workflow. Current verification baseline: backend unittest, frontend syntax checks, `npm run build`, and 5-test Playwright smoke all pass.

The 04:00Z wake closed the lint/format documentation and trend interval modeling items, and added a prose building-program contract for the currently seeded hybrid office program. Leave the multi-archetype template acceptance row unchecked for now: the README names future families, but only the AHU + VAV + lighting program is actually seeded/config-driven.

The 05:00Z wake closed the low-risk documentation cleanup only: `bas_app/README.md` no longer lists the verified trend interval as incomplete, and `bas_app/docs/architecture.md` now documents the intended simulator-to-repository boundary and Postgres entity map.

The 06:00Z wake implemented the first narrow runtime persistence slice: `backend.init_db` creates an SQLite `audit_logs` table, `AuditLogRepository` round-trips durable audit events, `backend/app.py` can use that repository when `BAS_DB_PATH` is set, and backend tests pass.

The 07:00Z wake extracted schedule update/exception handling into `backend/schedule_service.py`, command/release handling into `backend/command_service.py`, and promoted `backend/building_program.py` into a tiny template registry with the seeded `hybrid_office` contract plus a `vrf_doas` stub. Backend tests passed at 45 tests, and the acceptance row for business logic not being confined to route handlers was checked.

The 08:00Z wake added durable demo auth tables/repository and DB-backed `DemoAuthService` loading when `BAS_DB_PATH` is set, added a durable schedule JSON repository, and extracted alarm ack/shelve validation into `backend/alarm_service.py`. Backend tests passed at 51 tests. No frontend files changed.

The 09:00Z wake wired schedule persistence into runtime behind `BAS_DB_PATH`, added a durable alarm snapshot repository plus restart hydration for ack/shelve lifecycle state, and extracted point metadata validation/mutation into `backend/point_service.py`. Backend tests now pass at 58 tests. No frontend files changed, so the dark `graphic.html` theme alignment is unchanged.

The 10:00Z wake added the catalog persistence slice and the trend repository/schema slice. Catalog is runtime-wired: `CatalogRepository.from_env()` is used during `create_server()`, and tests prove no-DB defaults plus DB hydration.

The 11:00Z wake closed the trend runtime mismatch: `TrendRepository.from_env()` is wired into `BASHTTPServer`, `DemoSimulator.set_trend_history()` hydrates persisted samples, and backend restart/API coverage proves modified DB trend samples return from `/api/trends`. It also added `BAS_BUILDING_PROGRAM_TEMPLATE=vrf_doas` as a real alternate DOAS + VRF seed with backend coverage and README notes. No frontend files changed in the 11:00Z wake, so the dark `graphic.html` theme alignment is unchanged.

The 12:00Z wake implemented the building-program discovery slice: authenticated `GET /api/building-program` reports active template family, available template names, template summaries, and schedule category buckets. Backend tests cover default discovery, `vrf_doas` selection, catalog shape, metadata buckets, inference, and unknown-template fallback. The building-program acceptance row is now checked.

The 13:04Z critique verified the doc-only domain-model closure and checked that acceptance row. Backend tests pass at 69 tests, and frontend syntax checks pass. No frontend files changed, so dark `graphic.html` theme alignment is unchanged.

The 14:04Z critique verified the final documentation/auth closure. Recent app changes were documentation/smoke only: `bas_app/scripts/smoke_protected_reads.sh` now expects the current 13-point / 13-trended-point seeded catalog, and `bas_app/README.md` no longer lists stale incomplete acceptance gaps. Verification passed for `./scripts/smoke_protected_reads.sh`, `python3 -m unittest discover -s backend/tests`, `node --check frontend/app.js`, `node --check tests/frontend_smoke.spec.mjs`, `npm run build`, and `./scripts/smoke_frontend_e2e.sh`. The remaining two acceptance rows were checked. `REMOVE_CRON_WHEN_COMPLETE=false`, so cron will keep running unless a human flips it.

The 15:02Z critique found only a post-14:04Z frontend markup touch in `bas_app/frontend/index.html`; CSS, JS, backend, and tests were not modified. The markup still uses the existing dark BAS classes and did not drift from `frontend_example/graphic.html`. Verification passed for `./scripts/smoke_protected_reads.sh`, `python3 -m unittest discover -s backend/tests`, `node --check frontend/app.js`, `node --check tests/frontend_smoke.spec.mjs`, `npm run build`, and `./scripts/smoke_frontend_e2e.sh`.

The 16:01Z critique found no product-file changes after the 15:02Z pass. The 16:00 mini only updated checkpoint state to say no mini-sized app slice remained, and `bas_app/test-results/.last-run.json` was the only newer app-side file from the prior Playwright run. No skills changed after the previous critique. Acceptance remains fully checked; `REMOVE_CRON_WHEN_COMPLETE=false`, so cron remains armed.

The 17:02Z critique found the 17:00 mini was also bookkeeping-only: it updated `BUILD_CHECKPOINTS.md` to record no remaining mini-sized product slice and left `bas_app/`, skills, docs, and acceptance criteria untouched. No UI files changed, so the previously verified dark BAS alignment with `frontend_example/graphic.html` still stands. Acceptance remains fully checked, but scheduled automation remains armed because `REMOVE_CRON_WHEN_COMPLETE=false`.

The 18:02Z critique found the 18:00 mini was stabilization-only: it added the 17:35 `Done recently` line, touched `stop_mini_loop`, and skipped remaining minis. However, mtimes since the prior critique show `skills/web-app-bas/SKILL.md` and `skills/systemd-live-dev/SKILL.md` changed at 17:52-17:53Z and `bas_app/frontend/index.html` shares a 17:33Z mtime with `.env` and `acceptance_criteria.md`. The skill edits appear to focus on LAN dial-in, user-systemd, CORS, and post-wake runtime guidance; next wake should verify guardrail fit and symlink health before expanding any skill again. The frontend markup still uses the dark BAS shell classes and does not show obvious drift from `frontend_example/graphic.html`, but rerun frontend build/smoke if it changed again.

Next mini should treat this as release stabilization: no new product work unless the human gives scope, no new acceptance rows unless scope changes, and any touched surface should be verified narrowly. For frontend markup/style/script changes, run `npm run build` and `./scripts/smoke_frontend_e2e.sh`; for backend/runtime changes, run the backend unit suite and relevant smoke. Keep remote BAS URLs as `http://<server-lan-ip>:5173/` and `:8000`; keep real BACnet off by default.
