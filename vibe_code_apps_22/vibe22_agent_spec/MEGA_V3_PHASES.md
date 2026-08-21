# Vibe22 mega v3 program index

**Status (2026-08-21):** Dual-tariff research-long **finished**. Published pack under
`docs/results/` (draft PR [#114](https://github.com/bbartling/py-bacnet-stacks-playground/pull/114)).
Still Terminal B — A04 is **not** a transient-validated physics champion;
`long_campaign_allowed` remains false.

- Phase 2 W2A diagnosis: PR #111 — hypothesis-only with MCP evidence.
- Scaffold / hp67: PR #112 (`feat/vibe22-mega-scaffold-clean`).
- Launch-readiness merge: PR #113 — hp67 v2 failed champion; pilot passed;
  historical v2/flat run `research_long_20260819T211601Z` (not PRIMARY).
- **Action/tariff:** `research_action_contract_v3` (post-occupancy extension +
  schedule proof); PRIMARY `FLAT_PLUS_DEMAND` then SECONDARY
  `ILLUSTRATIVE_TOU_PLUS_DEMAND` with separate validation leaders.
- **Finished runs:**
  - PRIMARY: `research_long_flat_plus_demand_20260820T132506Z` → leader
    `trained_ppo_seed0` (≈ +$5.26, higher peak)
  - SECONDARY: `research_long_illustrative_tou_plus_demand_20260820T210304Z` →
    leader `trained_dqn_seed1` (≈ −$63.23 illustrative; energy down, demand/peak up)
- **Publication SoT:** [`RESULTS_PUBLICATION.md`](RESULTS_PUBLICATION.md) and
  `docs/results/vibe22_rl_poc_results.md`.
- Audit: `docs/audits/2026-08-20-vibe22-action-space-tariff-experiments.md`.

Do not retrain to “fix” publication. Disclose Dec billing floor; use
checked-school readiness wording; never mix flat/TOU dollars.

BACnet command authority = 0. Vibe19 untouched.
