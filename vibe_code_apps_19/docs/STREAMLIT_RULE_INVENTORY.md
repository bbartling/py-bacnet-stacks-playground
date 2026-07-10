# Streamlit Rule Inventory — Count Reconciliation

## Canonical count: **50**

Authoritative source: `app/rules/cookbook_catalog.py` (`CookbookRule` entries), recovered from
`develop:vibe_code_apps_19/fdd_app/backend/cookbook_rules.py`.

## User checklist vs cookbook

| User list item | Cookbook ID | Notes |
| --- | --- | --- |
| AHU-SIMUL-HEAT-COOL | **AHU-SIMUL** | Same rule, shorter ID in catalog |
| VAV-REHEAT-STUCK | **VAV-REHEAT** | Doc alias VAV-6 |
| SAT-HIGH | **FC13** | GL36 K — not a separate catalog entry |
| FAN-RUNTIME | — | SQL analytics; **not** in 50-rule pandas catalog |
| AVG-ZONE-TEMP | — | SQL analytics; **not** in 50-rule pandas catalog |
| ZONE-COMFORT-PCT | — | SQL analytics; **not** in 50-rule pandas catalog |
| FAULT-ELAPSED-HOURS | — | SQL rollup; **not** in 50-rule pandas catalog |

## SCHED-1, CMD-1, VLV-1

These **are** in the canonical 50 (extended families section), not extras.

## Why docs sometimes show 60+

Open-FDD documentation (`docs/rules/cookbook/`) lists individual SV-1…SV-7 rules, KPI rules,
and SQL-only rules. Python consolidates sensor checks into **SV-RANGE / SV-FLATLINE / SV-SPIKE / SV-STALE** sweeps.
**SV-4** (MAT mixing envelope) was removed as redundant with AHU GL36 FC2/FC3 and replaced by
**PID-HUNT-1** (suspected 0–100% control-output hunting across dampers/valves/fan cmds).

## No 53-rule count

No reference to exactly 53 named functions was found. Stale **48** counts in old agent specs
predate the final two extended-family rules.

## Generated metadata

- `configs/rule_inventory.yaml` — machine-readable inventory (auto-generated)
- `configs/rule_defaults.yaml` — slider metadata per rule (auto-generated)

Regenerate:

```powershell
python scripts/generate_rule_configs.py
```
