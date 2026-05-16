# Next directions (optional long-form)

Use **bas_build_spec/BUILD_CHECKPOINTS.md** as the primary ordered queue.

**Site-specific bind, devices, and HVAC** → **`memory/commissioning/PHASE_NOTEPAD.md`** only (not hard-coded here).

---

## PASTE INTO NEXT WAKE (copy from here)

```
Read GUARDRAILS.md, BUILD_CHECKPOINTS.md, this file, PHASE_NOTEPAD.md,
field-commissioning-phases/references/commissioning-ui-language.md,
rough_in_chat_since_last_wake.md, and bacnet-driver-lifecycle.

Site context: read PHASE_NOTEPAD.md § A–E (bind, NIC, devices, URLs, HVAC archetype).
Do not assume a fixed lab subnet — each OT job is unique.

PRIORITY A — Rough-in verification hygiene:
1. Update tests/frontend_smoke.spec.mjs to the current rough-in contract:
   5 driver rows, no "Simulator mock", "BACnet listener", title "Pending Who-Is",
   AHU IP from PHASE_NOTEPAD § C (not .113 typo), and no simulator device rows.
2. Isolate automated chat writes from guard/Playwright with temp
   BAS_COMMISSIONING_CHAT_PATH and BAS_COMMISSIONING_CHAT_SUMMARY_PATH, or
   preserve/restore runtime/rough_in_chat.json and summary after tests.
3. Fix bas_validate_wake_chat_slice.sh so populated PHASE_NOTEPAD § A/§ C is
   considered present; it should fail only when pinned bind/device context is
   missing from the wake export.
4. Keep public /rough-in/ labels field-facing per commissioning-ui-language.md.

PRIORITY B — BACnet Who-Is (ONLY if human checked BOTH boxes in BUILD_CHECKPOINTS § BACnet lab sign-off):
1. Who-Is on bind from PHASE_NOTEPAD § A (bacnet_scripts_example/ or bas_bacnet_lab_verify.sh).
2. Log I-Ams to memory/integrations/bacnet.md; update rough-in device table.
3. Post summary: bas_app/scripts/post_rough_in_chat_report.py
4. No writes on public rough-in.

If sign-off UNCHECKED: Priority A only; no UDP BACnet wire traffic.

Verify: targeted rough-in/CORS unit tests; node --check frontend/rough-in/app.js;
rough-in smokes including guard; npm run build; smoke_frontend_e2e.sh;
bas_validate_site_agnostic.sh; bas_validate_wake_chat_slice.sh.
```

---

## BACnet lab validation prompts

Combined operator + Codex prompt: **`cron_codex/state/PROMPT_bacnet_lab_validate.md`** (uses PHASE_NOTEPAD for all IPs/devices).

---

## Older context

Graphics, auth, persistence, and operator shell at `http://<lan-ip>:5173/` remain Phase 4 regression target.
