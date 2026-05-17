# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue.

**Site-specific bind, devices, and HVAC** → **`memory/commissioning/PHASE_NOTEPAD.md`** only (not hard-coded here).

---

## PASTE INTO NEXT WAKE (copy from here)

```
Read GUARDRAILS.md, BUILD_CHECKPOINTS.md, this file, PHASE_NOTEPAD.md,
rough_in_chat_since_last_wake.md, memory/integrations/bacnet.md,
memory/integrations/bacnet_discovery_latest.json,
field-commissioning-phases/references/commissioning-ui-language.md,
and bacnet-driver-lifecycle.

Site context: read PHASE_NOTEPAD.md § A–E (bind, NIC, devices, URLs, HVAC archetype).
Do not assume a fixed lab subnet — each OT job is unique.

Current wire result: latest discovery shows 3 I-Ams on
192.168.204.18/24:47808:
- 3456788 @ 192.168.204.12 (discovered, not yet staged)
- 3456790 @ 192.168.204.14 (expected VAV)
- 3456789 @ 192.168.204.13 (expected AHU)

Current live rough-in result from critique:
- /api/public/rough-in device_tree includes #3456788 as discovered_not_staged.
- /api/public/rough-in device_table returns exactly four polling contract
  rows: bind, VAV #3456790, AHU #3456789, sensor #3456788. No simulator/seed
  rows are present in the live payload verified by critique.
- /api/public/rough-in exposes point_scrape from
  memory/integrations/bacnet_point_samples_latest.json. Latest critique proof:
  2026-05-17T16:05:34Z, 3 targets, 3 ok, 8 samples,
  0 failures.
- Live tree point rows are one-decimal and verified by leaf-row Playwright
  selectors. The tree has `li.tree-node.tree-point-row` on present-value
  leaves, and the browser smoke proves at least one integer-like
  `present-value = 66.0` while rejecting raw long PV strings.
- /rough-in/ renders the point-scrape report card.
- /home/ben/bas_app/scripts/print_public_rough_in_proof.py prints a read-only
  proof summary from /api/public/rough-in, rejects malformed device_table rows,
  and works against the live API.
- cron/jobs.json has bas-wake-hourly at the operator-requested 0 */2 * * *.

PRIORITY A — Finish electrical MVP simplification:
1. The 2026-05-17T13:44Z tree request is implemented and full browser E2E
   passes. Preserve device rows showing device name/status and only last-poll
   metadata. Do not render device IP/address or verbose staging detail on
   depth-1 device rows.
2. Keep chat + BACnet NIC/bind + device tree as the primary rough-in surface.
   Move redundant engineering/proof surfaces (`network-table`, point-scrape
   report table, and the flat `device-table`) into native `<details>` advanced
   sections. Summary labels should still make it clear proof data exists.
3. Update the public rough-in Playwright smoke for the collapsed layout: assert
   the summaries, expand details, and preserve all existing proof checks for
   ports, point scrape, staged/discovered rows, no simulator rows, no device IPs
   on tree device rows, and rounded PVs.
4. Keep device labels/names: `#3456790 VAV`, `#3456789 AHU`, and `#3456788
   1-Wire DS18B20 / Pi temperature sensor`. Keep `3456788` status as
   **On wire (not in job list)** unless a human stages it.

PRIORITY B — Safety contracts:
1. Keep public `/rough-in/` read-only, no-login, and narrow.
2. Preserve safety contracts: public `/rough-in/` is read-only, no simulator
   rows in polling mode, protected writes remain blocked, and no Phase 2 writes
   are added.
3. Keep the operator-requested Codex cadence pinned to every 2 hours:
   `bas-wake-hourly` `0 */2 * * *`. Who-Is and point scrape stay 5-min workers.

PRIORITY C — Test cleanup:
1. Focused backend rough-in tests now pass; keep them green.
2. The current gate is green: `./scripts/smoke_frontend_e2e.sh` passes 6/6 as
   of the 2026-05-17T18:06Z critique. Keep it green after layout changes.
3. Avoid skill edits this wake unless a human explicitly asks.

Verify: ss -ltnp | rg ':(8000|5173)\b'; curl -sfS
http://127.0.0.1:8000/health; curl -sfS
http://127.0.0.1:8000/api/public/rough-in | jq '.device_tree[0].children[].children[].address'; focused
backend rough-in/build_device_tree tests; node --check frontend/rough-in/app.js;
node --check tests/frontend_smoke.spec.mjs; smoke_public_rough_in.sh;
smoke_public_rough_in_guard.sh; npm run build; smoke_frontend_e2e.sh;
bas_validate_cron_services.sh; bas_validate_site_agnostic.sh;
bas_validate_wake_chat_slice.sh.

Leave Phase 1 / Day 0 acceptance [ ] until second-workstation field verify and
real read-only point values, or a clearly documented device-side blocker, are
visible to the operator.
```

---

## BACnet lab validation prompts

Combined operator + Codex prompt: **`cron_codex/state/PROMPT_bacnet_lab_validate.md`** (uses PHASE_NOTEPAD for all IPs/devices).

---

## Older context

Graphics, auth, persistence, and operator shell at `http://<lan-ip>:5173/` remain Phase 4 regression target.
