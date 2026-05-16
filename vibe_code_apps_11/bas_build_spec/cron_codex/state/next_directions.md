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

PRIORITY A — Table/tree/API parity:
1. Fix /api/public/rough-in so the device table includes every discovered
   not-staged device from bacnet_discovery_latest.json, especially #3456788
   at 192.168.204.12, labeled "1-Wire DS18B20 / Pi temperature sensor".
2. Add a backend test that the public snapshot table has bind + all 3 discovered
   devices when polling is active. Keep the rough-in public route read-only.
3. Restart or refresh the live :8000/:5173 stack after edits. Prove live-source
   parity with curl: #3456788 must appear in the table and the tree with the
   same intended status semantics as source (discovered_not_staged unless
   intentionally staged).

PRIORITY B — Sensor/point data:
1. Start bounded read-only point/sensor scraping. Revise point_discovery.py or
   add a narrow companion script so it targets discovered remote device
   addresses/instances (192.168.204.12/.13/.14), not the local head-end
   bind object-list.
2. Store successful sample values or explicit failures in JSON for
   /api/public/rough-in.
3. If reads still fail, show an operator-visible blocker with device, address,
   object/property attempted, timestamp, and exact no-response/error. Do not
   present placeholders as live values.
4. Keep public rough-in read-only: no writes, no command UI, protected writes
   still 401/403 without proper auth. Keep simulator branding out of polling
   mode.

PRIORITY C — Automation hygiene:
1. Add/adjust a smoke for Codex wake cadence: bas-wake-hourly must remain every
   2 hours.
2. Do not edit skills this wake unless explicitly required; the previous wake
   already touched GUARDRAILS plus skill/reference files.

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
