# BACnet lab validation — single combined prompt (site-agnostic)

**Prerequisite:** Human checks **both** boxes in `BUILD_CHECKPOINTS.md` § BACnet lab sign-off.

**All bind / device / IP values:** read **`memory/commissioning/PHASE_NOTEPAD.md` § A and § C** — do not hard-code another site's LAN.

**Use this one block:**
1. Paste into **rough-in chat** — records operator intent.
2. Paste into **manual Codex wake** — same text; Codex executes Part B.

---

## Combined prompt (copy all below)

```
=== Part A — Operator / rough-in chat record ===

BACnet lab validation request (after BUILD_CHECKPOINTS § BACnet lab sign-off is checked):

Use bind, NIC, and expected devices from PHASE_NOTEPAD.md (§ A, § C).
1. Who-Is / I-Am — match each staged device (instance + IPv4 if listed).
2. Driver/stack healthy on wire (not simulator-only on /rough-in/).
3. Read sample present-values; show comm healthy / stale / offline in Devices table.
4. Post pass/fail summary back into this chat when done.
Read-only — no writes.

=== Part B — Codex execution (same wake) ===

Read: BUILD_CHECKPOINTS.md, GUARDRAILS.md, rough_in_chat_since_last_wake.md,
PHASE_NOTEPAD.md, memory/integrations/bacnet.md, bacnet-driver-lifecycle,
commissioning-ui-language.md, bacnet_scripts_example/README.md.

Steps:
1. If lab sign-off UNCHECKED — stop; post to chat that Who-Is is blocked.
2. If sign-off IS checked:
   a. Who-Is on bind from PHASE_NOTEPAD § A (point_discovery.py or bas_bacnet_lab_verify.sh + .env).
   b. Append to memory/integrations/bacnet.md.
   c. Update /api/public/rough-in device rows from I-Ams vs § C staged list.
   d. cd /home/ben/bas_app && python3 scripts/post_rough_in_chat_report.py --file <report.md>
3. Verify: bas_validate_site_agnostic.sh; curl /api/public/rough-in; rough-in smokes.

No writes. Do not check Phase 1 acceptance [x] without human field verify.
```

---

## Run

```bash
CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
$CR/bin/bas_validate_site_agnostic.sh
MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_wake.sh
```
