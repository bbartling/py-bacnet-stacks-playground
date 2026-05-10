# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue. Add detail here only when a wake needs extra context beyond that file.

## 2026-05-10 critique handoff

`/home/ben/bas_app` now has a first scaffold from the 15:29 UTC mini wake: Python backend package, React/TypeScript frontend package, root README, and a compose stub. Treat `BUILD_CHECKPOINTS.md` as the source of truth for the ordered queue.

Important critique findings:

- Backend currently has `/health` only. Add one seeded public demo API before deeper features.
- Frontend currently uses static arrays. Wire it to the demo API once that endpoint exists.
- Compose is not truly runnable yet because `docker-compose.yml` has build contexts but no Dockerfiles.
- UI is dark and roughly aligned with `graphic.html`, but the operator shell should tighten toward `schedule_example.html` tokens and smaller BAS table/card chrome.
- Keep all data simulator-only. Do not run BACnet discovery or writes.

Good next slice:

- Add backend seed data + `/api/demo/site` or `/api/demo/tree`.
- Smoke `/health` and the demo API.
- Clean `__pycache__/`, add `.gitignore`, and record verification in `BUILD_CHECKPOINTS.md`.
