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

PRIORITY A — Commissioning record integrity:
1. Sync PHASE_NOTEPAD.md § B/E with the latest operator fact:
   "VRF + DOAS with expected VAV boxes." Preserve § A bind and § C expected
   devices; append a chronological note.
2. Update memory/integrations/bacnet.md so it no longer says "Who-Is not run
   yet"; record the successful I-Am list and extra device 3456788.
3. Reconcile the "human only" BACnet sign-off wording with the current
   BAS_BACNET_AUTO_COMMISSION behavior, without enabling writes.

PRIORITY B — Rough-in device/polling UX:
1. Ensure /api/public/rough-in and /rough-in/ show discovered vs staged
   devices with field-facing statuses: Online, Discovered not staged, No I-Am,
   Stale/Offline. Keep simulator branding out of public rough-in.
2. Attempt read-only sample present-value scraping for 2-5 points per expected
   device. If object-list no-response blocks this, try only documented safe
   explicit objects; otherwise show "object-list no-response" clearly in the
   table and chat summary.
3. Keep public rough-in read-only: no writes, no command UI, protected writes
   still 401/403 without proper auth.
4. Keep guard/Playwright smokes on temp BAS_COMMISSIONING_CHAT_PATH and
   BAS_COMMISSIONING_CHAT_SUMMARY_PATH.

Verify: curl /api/public/rough-in; targeted backend rough-in tests;
node --check frontend/rough-in/app.js; smoke_public_rough_in.sh;
smoke_public_rough_in_guard.sh; npm run build; smoke_frontend_e2e.sh;
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
