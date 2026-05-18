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

Current live rough-in result from 2026-05-18T12:02Z critique:
- /api/public/rough-in device_tree includes #3456788 as discovered_not_staged.
- /api/public/rough-in device_table returns exactly four polling contract
  rows: bind, VAV #3456790, AHU #3456789, sensor #3456788. No simulator/seed
  rows are present in the live payload verified by critique.
- /api/public/rough-in exposes point_scrape from
  memory/integrations/bacnet_point_samples_latest.json. Latest critique proof:
  generated_at_utc 2026-05-18T11:55:33Z, 3 targets, 3 ok, 8 samples,
  0 failures.
- Live tree point rows are one-decimal and verified by leaf-row Playwright
  selectors. The tree has `li.tree-node.tree-point-row` on present-value
  leaves, and the browser smoke proves at least one integer-like
  `present-value = 66.0` while rejecting raw long PV strings.
- /rough-in/ renders the point-scrape report card.
- /rough-in/ now keeps chat + BACnet NIC/bind + device tree as the primary
  first-view surface. The LAN/listener table, point-scrape report, and flat
  device/point proof table are collapsed by default in native `<details>`
  advanced sections with explicit `Proof rows` badges; Playwright verifies
  they start closed, then expands them before checking proof rows as of the
  2026-05-17T22:07Z critique.
- /rough-in/ source now includes a visible `#device-tree-proof` line under the
  device tree header with latest point-scrape time and
  `bacnet_point_samples_latest.json` source. Full browser E2E still verifies the
  line (`./scripts/smoke_frontend_e2e.sh`, 6/6 as of the 2026-05-18T04:09Z
  critique). The 2026-05-18T12:02Z critique found no source/UI changes and
  did not rerun the full browser suite.
- /home/ben/bas_app/scripts/print_public_rough_in_proof.py prints a read-only
  proof summary from /api/public/rough-in, rejects malformed device_table rows,
  and works against the live API.
- cron/jobs.json has bas-wake-hourly at the operator-requested 0 */2 * * *.

PRIORITY A — Stabilize electrical MVP simplification:
1. Freeze the implemented first-view workflow unless there is a real defect:
   chat + BACnet NIC/bind + device tree are visible; `network-table`,
   point-scrape report table, and flat `device-table` remain collapsed in
   native `<details>` advanced/proof sections by default.
2. If physically possible, perform the real second-workstation Phase 1 check
   from another LAN machine at `http://192.168.204.18:5173/rough-in/`: no
   login, chat renders, bind/NIC and device tree render, proof sections open,
   no simulator rows appear, and browser console has no errors. If not possible,
   document that blocker and leave acceptance unchecked.
3. Keep the existing public rough-in Playwright assertions intact: details
   closed/openable, ports, point scrape, staged/discovered rows, no simulator
   rows, no device IPs on tree device rows, and rounded PVs.
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
2. The full E2E gate is green at the 2026-05-18T04:09Z critique, including
   browser proof of the `#device-tree-proof` line. The 2026-05-18T10:03Z
   and 2026-05-18T12:02Z critiques reran live HTTP/cron validators only because no UI/source changed.
   Do not churn UI just to create work.
3. Avoid skill edits this wake unless a human explicitly asks; if no app defect
   is found, verify and leave a concise `Done recently` row only.

Verify: ss -ltnp | rg ':(8000|5173)\b'; curl -sfS
http://127.0.0.1:8000/health; curl -sfS
http://127.0.0.1:8000/api/public/rough-in | jq
'{device_rows:(.device_table|length), tree:.device_tree[0].children|map({id:.device_instance,status:.status,label:.label}), point_scrape:{generated_at_utc:.point_scrape.generated_at_utc, targets:.point_scrape.target_count, ok:.point_scrape.ok_count, samples:.point_scrape.sample_count, failed:.point_scrape.failed_count}}';
python3 -m pytest backend/tests/test_app.py -k 'rough_in or bacnet_device_tree' -q;
node --check frontend/rough-in/app.js; node --check tests/frontend_smoke.spec.mjs;
smoke_public_rough_in.sh; smoke_public_rough_in_guard.sh; npm run build;
smoke_frontend_e2e.sh or focused Playwright/browser proof if runnable;
bas_validate_cron_services.sh;
bas_validate_site_agnostic.sh; bas_validate_wake_chat_slice.sh.

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
