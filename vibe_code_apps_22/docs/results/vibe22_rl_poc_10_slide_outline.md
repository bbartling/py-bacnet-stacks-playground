# Vibe22 RL PoC — 10-slide evidence outline

Honesty: SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY; NO VERIFIED 285 kW DEMAND REDUCTION CLAIM

> The completed RL and exhaustive fixed-policy campaigns were internally paired EnergyPlus screening experiments over December validation weather using OBSERVED_BAS_INCUMBENT_V2. They did not test reduction of the approximately 285 kW January billed-demand event.

## Slide 1: School and winter demand problem

- **Primary claim:** Winter electric demand at Lakeside is a billing and operations problem, not a training-curve problem.
- **Figure path:** `docs/results/figures/peak_and_readiness_tradeoff.png`
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_provenance.json`
  - `$SITE_ROOT/utilities/electricity_utility_demand.csv`
- **Speaker notes:** Open with utility winter peaks and school-day comfort constraints; do not lead with RL rewards.
- **Limitation / caveat:** Utility bills are site evidence; RL dollars are modeled under illustrative tariffs.
- **Source / provenance:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY

## Slide 2: BAS, utility and weather evidence

- **Primary claim:** Campaigns replayed observed_bas_incumbent_v2 (68/64 scheduled), not a continuous 68/74 thermostat claim.
- **Figure path:** `docs/results/figures/representative_daily_control_plan.png`
- **Supporting artifacts:**
  - `contracts/observed_bas_incumbent_v2.json`
  - `docs/results/baseline_evidence_resolution.json`
- **Speaker notes:** State the possible field conflict (continuous 68/74) without retconning the campaign baseline.
- **Limitation / caveat:** Modeled savings are not verified versus actual BAS operation.
- **Source / provenance:** baseline_contract unchanged for historical campaigns

## Slide 3: A04 calibration and physics limitations

- **Primary claim:** A04 is the research IDF; it is not a transient-validated physics champion.
- **Figure path:** _(none — artifacts only)_
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_provenance.json`
  - `idf_sha256=212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683`
- **Speaker notes:** Keep Terminal B / research limits visible on every A04 claim.
- **Limitation / caveat:** A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION
- **Source / provenance:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY

## Slide 4: Six-zone EnergyPlus Gym

- **Primary claim:** Actions actuate six DualSP heating schedules; school occupancy calendar is immutable.
- **Figure path:** `docs/results/figures/representative_daily_control_plan.png`
- **Supporting artifacts:**
  - `eplus_gym/control_v2.py`
  - `contracts/school_calendar_v2.json`
- **Speaker notes:** Show school window vs heating recovery; extension does not invent holiday occupancy.
- **Limitation / caveat:** Cooling remains approximately fixed (~74/85); not optimized.
- **Source / provenance:** research_action_contract_v3

## Slide 5: PPO/DQN action spaces

- **Primary claim:** PPO Box10 + DQN discrete table under research_action_contract_v3; continuous 68/70 reachable.
- **Figure path:** _(none — artifacts only)_
- **Supporting artifacts:**
  - `eplus_gym/rl/research_spaces.py`
  - `action_contract=research_action_contract_v3`
  - `obs_schema=v4 dim=206`
- **Speaker notes:** Do not describe the discrete table as an exhaustive LIVE screen (NOT_RUN).
- **Limitation / caveat:** docs/results/vibe22_rl_poc_exhaustive_discrete_screen.json status NOT_RUN
- **Source / provenance:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY

## Slide 6: Reward and paired-baseline calculation

- **Primary claim:** Validation leaders use deterministic costs + readiness, never training mean reward.
- **Figure path:** `docs/results/figures/cost_decomposition_by_tariff.png`
- **Supporting artifacts:**
  - `eplus_gym/rl/reward_v2.py`
  - `deterministic_validation_plus_readiness_multi_seed; never training mean_reward; never mix tariffs`
- **Speaker notes:** Explain energy vs incremental demand; readiness checked only on school days.
- **Limitation / caveat:** December billing floor opened at 0 kW on 2025-12-15.
- **Source / provenance:** docs/results/vibe22_rl_poc_results.md December disclosure

## Slide 7: Experiment scale and provenance

- **Primary claim:** Distinguish RL transitions (8192×4), validation arm-days (187), and unrecorded E+ process launches.
- **Figure path:** _(none — artifacts only)_
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_provenance.json`
  - `C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\reports\eplus_gym\rl\research_long_flat_plus_demand_20260820T132506Z`
  - `C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\reports\eplus_gym\rl\research_long_illustrative_tou_plus_demand_20260820T210304Z`
- **Speaker notes:** Say 'not recorded' for process count; do not invent.
- **Limitation / caveat:** actual_energyplus_process_launches is null in manifests.
- **Source / provenance:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY

## Slide 8: Flat-tariff result

- **Primary claim:** PRIMARY validation leader `trained_ppo_seed0` ≈ $7628.91 vs incumbent ≈ $7623.65 (Δ $+5.26); peak 233.8 vs 201.9 kW.
- **Figure path:** `docs/results/figures/cost_decomposition_by_tariff.png`
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_arm_scorecard.csv`
  - `docs/results/vibe22_rl_poc_results.json`
- **Speaker notes:** Leader did not reduce peak or cost. Readiness: Ready on 5/5 checked school days; 12 non-school days were not subject to the school-start readiness gate. Incumbent: Ready on 0/5 checked school days; 12 non-school days were not subject to the school-start readiness gate.
- **Limitation / caveat:** Never say 17/17 school readiness; use checked-school wording.
- **Source / provenance:** FLAT_PLUS_DEMAND only

## Slide 9: Illustrative-TOU result

- **Primary claim:** SECONDARY validation leader `trained_dqn_seed1` illustrative Δ $-63.23; energy down, demand/peak up.
- **Figure path:** `docs/results/figures/peak_and_readiness_tradeoff.png`
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_arm_scorecard.csv`
  - `C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\reports\eplus_gym\rl\research_long_illustrative_tou_plus_demand_20260820T210304Z`
- **Speaker notes:** Do not compare absolute $ to PRIMARY. TOU is illustrative.
- **Limitation / caveat:** TOU TARIFF IS ILLUSTRATIVE — NOT VERIFIED UTILITY PRICING
- **Source / provenance:** ILLUSTRATIVE_TOU_PLUS_DEMAND only; never mix rankings

## Slide 10: Honest conclusion and deployment boundary

- **Primary claim:** Simulation-only research PoC; not operational DSM; no BACnet authority; no pristine locked test.
- **Figure path:** `docs/results/figures/representative_day_outcomes.png`
- **Supporting artifacts:**
  - `docs/results/vibe22_rl_poc_results.md`
  - `docs/results/vibe22_rl_poc_exhaustive_discrete_screen.json`
- **Speaker notes:** End on boundaries: Terminal B A04 limits, Dec floor disclosure, baseline contract.
- **Limitation / caveat:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY
- **Source / provenance:** SIMULATION-ONLY RL RESEARCH; NOT VALIDATED FOR OPERATIONAL DSM; NO PRISTINE LOCKED TEST; A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION; TOU TARIFF IS ILLUSTRATIVE; CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2; NO BACNET COMMAND AUTHORITY

## Slide addendum: Discrete grid comparator

- **Primary claim:** Exhaustive fixed-policy discrete v3 screen found GRID_LOWER_COST_AND_READY leaders vs PPO (flat) and DQN (TOU) on the same validation window; tariff vector changed selected extension.
- **Figure path:** `docs/results/grid_search/figures/grid_candidate_cost_landscape.png`
- **Supporting artifacts:**
  - `docs/results/grid_search/grid_search_verdict.json`
  - `docs/results/grid_search/grid_search_compute_comparison.json`
  - `contracts/grid_search_experiment_v1.json`
- **Speaker notes:** Emphasize retrospective validation comparison; Dec floor disclosure; daily adaptive NOT_RUN.
- **Limitation / caveat:** Not operational DSM; mega Phase 10 scaffold is not this experiment.
- **Source / provenance:** LIVE ContinuityPlant screen under SITE_ROOT; compact pack only in git.

## Slide addendum: Two-month frozen-policy replay

- **Primary claim:** Dec 2025–Jan 2026 retrospective replay compares seven frozen strategies against actual CS 351075 utility bills (kWh/peak physical table; illustrative flat/TOU costs kept separate).
- **Figure path:** `docs/results/two_month_policy_replay/figures/fig06_pareto_kwh_peak.png`
- **Supporting artifacts:**
  - `docs/results/two_month_policy_replay/run_manifest.json`
  - `docs/results/two_month_policy_replay/two_month_decision_table.csv`
  - `vibe22_agent_spec/TWO_MONTH_POLICY_REPLAY.md`
- **Speaker notes:** PPO/DQN use full obs v4 (not Jan 26 zero-obs probe). Do not rank actual bill against illustrative tariff totals.
- **Limitation / caveat:** RETROSPECTIVE_CONTAMINATED; Dec overlaps training; continuous-68 is heating-only sensitivity.
- **Source / provenance:** LIVE EnergyPlus subprocess-per-strategy; BACnet commands 0.
