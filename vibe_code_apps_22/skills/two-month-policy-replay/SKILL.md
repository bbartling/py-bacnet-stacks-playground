---
name: two-month-policy-replay
description: >-
  Dec 2025–Jan 2026 LIVE EnergyPlus frozen-policy replay for seven strategies
  vs actual utility bills. Full obs v4 for PPO/DQN (no zero-obs). Subprocess
  per strategy. Publish pack under docs/results/two_month_policy_replay/.
  Use when running, resuming, or publishing the two-month cost/physical report.
---

# Two-month frozen-policy replay

**Claim:** RETROSPECTIVE ENERGYPLUS POLICY SCREENING · ILLUSTRATIVE TARIFFS · NO BACNET.

## When to use

- Running or resuming the 62-day LIVE replay
- Publishing CSVs/figures after SITE_ROOT runs complete
- Answering peak/kWh/cost questions for Dec+Jan vs CS 351075 utility

## Hard rules

- **Never** use zero-obs for PPO/DQN (unlike Jan 26 cold-day bridge diagnostic)
- **Never** merge flat vs TOU cost rankings
- **Never** rank actual utility bill against illustrative tariff totals
- **Never** fabricate invoice energy/demand split — use `NOT_AVAILABLE_FROM_SOURCE_INVOICE`
- One EnergyPlus subprocess per strategy (`--worker-json` pattern)

## CLI

```powershell
py -3.12 scripts/vibe22_two_month_policy_replay.py --site-root $env:SITE_ROOT --strategy all --resume
py -3.12 scripts/vibe22_two_month_policy_replay.py --site-root $env:SITE_ROOT --publish-only --site-run-dir <SITE_RUN_DIR>
```

## Spec

[`../../vibe22_agent_spec/TWO_MONTH_POLICY_REPLAY.md`](../../vibe22_agent_spec/TWO_MONTH_POLICY_REPLAY.md)

## Related

- [`../rl-daily-dsm/SKILL.md`](../rl-daily-dsm/SKILL.md)
- [`../../docs/results/two_month_policy_replay/README.md`](../../docs/results/two_month_policy_replay/README.md)
