# Codex wake — electrical phase UX simplify (rough-in only)

Paste for one focused wake (`MINI_INVOCATIONS_PER_WAKE=1` recommended).

```
Read: BUILD_CHECKPOINTS.md, commissioning-ui-language.md (electrical MVP section),
ELECTRICAL_PHASE_ARCHITECTURE.md, field-commissioning-phases.

Goal: /rough-in/ must sell as a simple electrician dashboard — not an engineer debug console.

Electrical phase MVP (only these primary surfaces):
1. **BACnet NIC / bind** — one card: bind string, NIC name, last Who-Is time, I-Am count, next cron runs.
2. **Device + point tree** — bind → device (#instance, IP, Online / On wire) → children show
   `object present-value = <value>` from bacnet_point_samples_latest.json (5-min scrape).
   Do NOT show "Point scrape blocked" when samples exist.
3. **Commissioning chat** — operator notes only; instant ack = **next cron** line. **Codex** posts critique + minis after each wake. **No worker posts** to chat (discovery/scrape live on tree only).

De-scope / hide for this phase:
- Collapse duplicate tables (driver + networking + flat device table + huge point-scrape grid)
  into tree + one bind card unless a row is truly needed.
- Remove engineer jargon in operator labels: prefer "On wire (not in job list)" over
  "discovered_not_staged" in visible UI text.
- Do not add writes, schedules, alarms, or Phase 2 features.

Workers (already configured — verify only):
- Who-Is: bas-bacnet-discovery-poll every 5 min
- Point scrape: bas-bacnet-point-scrape every 5 min
- Codex: bas-wake-hourly 0 */3 * * * UTC
- Crontab: */5 * * * * bas_cron_scheduler.sh run-due

Verify: curl /api/public/rough-in; smoke_public_rough_in.sh; one manual tree check in browser.

Append Done recently in BUILD_CHECKPOINTS.
```
