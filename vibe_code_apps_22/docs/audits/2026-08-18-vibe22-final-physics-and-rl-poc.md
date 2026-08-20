# Vibe22 final physics repair + research RL PoC (2026-08-18)

**Terminal: B**

No physics champion. Bounded real-EnergyPlus PPO/DQN research PoC ran on A04 and is labeled `RESEARCH_POC_ALLOWED` / `SIMULATION-ONLY RESEARCH POC`. `SIMULATION_TRAINING_READY` is false. `OPERATIONAL_DSM_READY` is false. `long_campaign_allowed` remains false. BACnet commands = 0. Vibe19 untouched. This is not “implementation complete.”

**Claim labels:** `SIMULATION_ONLY_RESEARCH_POC` · `NOT VALIDATED FOR OPERATIONAL DSM` · `NO BACNET COMMAND AUTHORITY` · `A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED`

Isolation: worktree `.worktrees/feat-vibe22-final-physics-rl-poc` from `feat/vibe22-live-trackb-long-rl-readiness` @ `7ca13a60`. Branch `feat/vibe22-final-physics-rl-poc`. Scope `vibe_code_apps_22/` only. Stacked **draft** PR against `feat/vibe22-live-trackb-long-rl-readiness`. Do not merge.

Machine-readable: [`figures/vibe22_final_physics_rl/`](figures/vibe22_final_physics_rl/).

## Handoff

| Field | Result |
| --- | --- |
| Terminal | **B** |
| Champion | **none** |
| A04 SHA-256 (CRLF) | `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683` |
| A04 SHA-256 (LF) | `080ab87797c78df0c8efb257a52bba97f550ee628ec4bd1333801b2e104b21eb` |
| A04 git blob | `03d3ba368e70e5206773191d292dfe4ca91b8774` |
| Track B research copy SHA-256 | `40fb33e863e5d04cabf087be42b74cc38de67d5030a2534e54847a98aa54029a` |
| Track C1 SHA-256 | `e9be543082e076fc861f97ad4e2a7a46b9538a3f8c5b6413cbd6d25a476e7be6` (gitignored candidate tree) |
| Track C2 SHA-256 | `47e70c8dd1f3ce3788a2c516b30bbd0c0307fb426ed92f44188039da569fbb53` |
| Staged EPW SHA-256 | `87d7d9bfca7de4ac5b905ec1a65defc7622a78dac9444fc55cdef618ddf91fb2` |
| EnergyPlus | **26.1.0-6f2e40d102** |
| Prior Track B LIVE matrix | **37** reports; first LIVE scored-runtime W2A **2106** / warmup **5332** (bound **0**) |
| Superseded two-pass W2A | **3780** scored (tree kept) |
| Instrumented Track B CLI day | scored **738** / warmup **4657**; active invalid-domain **759** / 1920 classified rows |
| Track C1 one-day W2A | scored **822** / warmup **5778**; 9 coils; freeze **603.05 kW**; 3-day skipped |
| Track C2 base one-day W2A | scored **2016** / warmup **13032**; hard-size **800 kW**; 3-day skipped |
| C3 | skipped (unverified A04 EquationFit; no valid multi-speed points) |
| Frozen ramp | **2.651 °F / 15 min** (not raised). A04 postfix `ramp_gate.json` remains `passed=false` |
| Monthly / demand / load-shape screens | **not run** (blocked by W2A) |
| `active_rl_model_v1.json` | `idf_path=null`, `long_campaign_allowed=false` |
| `research_rl_model_v1.json` | A04 twin; `research_poc_allowed=true`; other ready flags false |
| Research twin | `A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED` |
| PPO/DQN | 2 seeds × PPO+DQN, 4 timesteps, `research_poc` config, `research_action_contract_v1` |
| Valid logged transitions | 4 per algo/seed (16 total logged steps) |
| Checkpoints | 4 manifests (`rng` + `valid_transition_count` + IDF/EPW hashes) |
| Eval | incumbent baseline-only; continuous-70 and shallow vs incumbent; no candidate-as-baseline |
| Winner | **none** (`not_mean_training_reward`) |
| Wall clock | **28.5 s** (6 h cap unused; this host’s 1-day CLI is ~2 s) |
| Locked unseen | **NO LOCKED UNSEEN TEST AVAILABLE** (January 2026 used as development evidence) |
| `SIMULATION_TRAINING_READY` | **false** |
| `RESEARCH_POC_ALLOWED` | **true** |
| `OPERATIONAL_DSM_READY` | **false** |
| Vibe19 | untouched |
| BACnet | none |
| MCP | inspect succeeded; `validate_idf` eppy TypeError **not** claimed as validation; bounded days used EnergyPlus CLI |

## Phase 0 — diagnose

EnergyPlus MCP (`user-energyplus`) loaded A04 and the Track B child, summarized zones/loops/schedules/settings, and listed configured outputs. `validate_idf` failed inside eppy (`Idf_MSequence + Idf_MSequence`). Executable path was already `C:\EnergyPlusV26-1-0\energyplus.exe`. Bounded discovery/instrumented days used `eplus_gym/energyplus_cli.py`, not MCP annual runs.

RDD was empty until `Output:VariableDictionary` + `OutputControl:Files` RDD=Yes. Then 615 names. Confirmed (not guessed): `Heating Coil Electricity Rate`, `Heating Coil Source Side Mass Flow Rate`, `Heating Coil Runtime Fraction`, `Heating Coil Air Mass Flow Rate`.

Active invalid-domain: `runtime_fraction > 0.01 AND actual/rated air < 0.25`. Track B CLI 2026-01-12: raw scored W2A **738**, trajectory invalid-domain **759**, concentrated on SequentialLoad **small** banks vs full-zone design flow.

Sanitized evidence matrix (no client identity) is in [`figures/vibe22_final_physics_rl/sanitized_evidence_matrix.json`](figures/vibe22_final_physics_rl/sanitized_evidence_matrix.json). 67 heat-pump **records** are not 67 proven identical units.

## Phase 1–3 — Track C sequential (not a matrix)

**C1:** keep 9 zones / 6 RL groups; one aggregated W2A per zone; freeze explicit capacities from the autosize eio onto a CRLF-safe child. Total heating **603.05 kW** (below the 675–940 kW screening range). One development day: 0 severe/fatal, scored W2A **822**. Champion bound is 0 → **no 3-day LIVE screen**.

**C2:** hard-size aggregate heating **800 kW** (base; not forced to 791). One day: scored W2A **2016**. Worse, not a champion.

**C3:** skipped.

January 2026 remains development evidence, not holdout. Frozen ramp was not raised. Capacitance multipliers were not applied (no calibrated BAS decay).

## RL Branch B

```text
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --execute-live --site-root $env:SITE_ROOT
```

Missing confirm → exit 4. `operator-pay-experiment --mode full` stays exit 4. Research contract cannot set `long_campaign_allowed=true`. `FakeContinuityPlant` is refused. Eight live `eplusout.err` files: EnergyPlus **26.1.0-6f2e40d102**, 0 severe/fatal, `completed_successfully`. PPO seed0 logged four unique schedule fingerprints on 2025-12-08/09. Facility kW stayed finite and below 400 (peaks ≈186–202 kW). Paired eval distinguishes incumbent vs continuous-70 vs shallow. Mean training reward is **not** used to pick a winner. Display paycheck remains reporting-only. Tariffs `ILLUSTRATIVE`.

## Plots

Twelve figures in [`figures/vibe22_final_physics_rl/plots/`](figures/vibe22_final_physics_rl/plots/). Watermarks used: `DIAGNOSTIC FAILED MODEL` (1–5) and `SIMULATION-ONLY RESEARCH POC` (6–12). `VALIDATED CHAMPION CAMPAIGN` was **not** used.

## Future agents

1. Inspect IDF/RDD with EnergyPlus MCP before IDF edits. Do not guess Output:Variable names.
2. MCP cannot rewrite W2A banks; Track C stays in Python.
3. Do not launch another 30–40 cell matrix.
4. Do not update `active_rl_model_v1.json` without every champion gate, including active invalid-domain = 0 **and** raw scored-runtime W2A = 0.
5. Research fallback: `research-poc` only. Never `--mode full`.
